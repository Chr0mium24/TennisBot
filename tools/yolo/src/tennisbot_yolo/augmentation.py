from __future__ import annotations

import argparse
import json
import random
import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .dataset import (
    IMAGE_SUFFIXES,
    PixelBox,
    format_yolo_box,
    iter_image_paths,
    label_path_for_image,
    pixel_to_yolo_box,
    read_excluded_paths,
    read_yolo_labels,
    safe_relative_path,
    yolo_to_pixel_box,
)
from .paths import DEFAULT_DATASET_ROOT, DEFAULT_RUNS_ROOT, DEFAULT_SPRITES_ROOT, REPO_ROOT, TOOL_ROOT
from .sprites import require_cv2_numpy


DEFAULT_AUGMENT_CONFIG = TOOL_ROOT / "configs" / "augmentation.toml"
DEFAULT_OUTPUT_ROOT = DEFAULT_RUNS_ROOT / "copy_paste_aug"


@dataclass(frozen=True)
class BackgroundRecord:
    image_rel_path: str
    image_path: Path
    label_path: Path
    has_label_file: bool
    labels: list[str]
    boxes: list[PixelBox]
    is_negative: bool


@dataclass(frozen=True)
class SpriteRecord:
    sprite_id: str
    image_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class PixelLabel:
    class_id: int
    box: PixelBox


@dataclass(frozen=True)
class AugmentationResult:
    output_root: Path
    generated: int
    skipped: int
    manifest: Path
    report: Path


def read_config(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _range(config: dict[str, Any], section: str, key: str, default: tuple[float, float]) -> tuple[float, float]:
    values = config.get(section, {}).get(key, list(default))
    if not isinstance(values, (list, tuple)) or len(values) != 2:
        raise ValueError(f"{section}.{key} must be a two-value range")
    lo = float(values[0])
    hi = float(values[1])
    if lo > hi:
        raise ValueError(f"{section}.{key} range must be ordered")
    return lo, hi


def _int_range(config: dict[str, Any], section: str, key: str, default: tuple[int, int]) -> tuple[int, int]:
    lo, hi = _range(config, section, key, (float(default[0]), float(default[1])))
    return int(lo), int(hi)


def _resolve_config_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _section_path(config: dict[str, Any], section: str, key: str, default: Path) -> Path:
    value = config.get(section, {}).get(key)
    return _resolve_config_path(Path(value)) if value else default


def _section_int(config: dict[str, Any], section: str, key: str, default: int) -> int:
    return int(config.get(section, {}).get(key, default))


def _section_float(config: dict[str, Any], section: str, key: str, default: float) -> float:
    return float(config.get(section, {}).get(key, default))


def _section_bool(config: dict[str, Any], section: str, key: str, default: bool) -> bool:
    return bool(config.get(section, {}).get(key, default))


def resolve_config(config_path: Path) -> dict[str, Any]:
    config = read_config(config_path)
    pipeline = config.get("augmentation", {}).get("pipeline", "copy_paste")
    if pipeline != "copy_paste":
        raise ValueError(f"unsupported augmentation pipeline: {pipeline!r}")

    dataset_root = _section_path(config, "inputs", "dataset_root", DEFAULT_DATASET_ROOT)
    resolved = {
        "augmentation": {"pipeline": pipeline},
        "inputs": {
            "dataset_root": dataset_root,
            "images_root": dataset_root / "images",
            "labels_root": dataset_root / "labels",
            "sprites_root": _section_path(config, "inputs", "sprites_root", DEFAULT_SPRITES_ROOT / "approved"),
            "excluded_file": _section_path(config, "inputs", "excluded_file", dataset_root / "excluded_images.txt"),
        },
        "output": {
            "root": _section_path(config, "output", "root", DEFAULT_OUTPUT_ROOT),
            "count": _section_int(config, "output", "count", 1000),
            "seed": _section_int(config, "output", "seed", 42),
            "image_format": str(config.get("output", {}).get("image_format", "jpg")).lower(),
            "jpeg_quality": _section_int(config, "output", "jpeg_quality", 92),
        },
        "selection": {
            "allow_labeled_backgrounds": _section_bool(config, "selection", "allow_labeled_backgrounds", True),
            "prefer_negative_backgrounds": _section_bool(config, "selection", "prefer_negative_backgrounds", True),
            "require_label_file_backgrounds": _section_bool(config, "selection", "require_label_file_backgrounds", False),
            "paste_per_image": _int_range(config, "selection", "paste_per_image", (1, 1)),
        },
        "negative_augmentation": {
            "count": _section_int(config, "negative_augmentation", "count", 0),
        },
        "originals": {
            "include": _section_bool(config, "originals", "include", False),
        },
        "split": {
            "val_ratio": _section_float(config, "split", "val_ratio", 0.0),
            "seed": _section_int(config, "split", "seed", _section_int(config, "output", "seed", 42)),
        },
        "background": {
            "brightness": _int_range(config, "background", "brightness", (-25, 25)),
            "contrast": _range(config, "background", "contrast", (0.85, 1.15)),
            "blur_probability": _section_float(config, "background", "blur_probability", 0.1),
            "blur_kernel": _int_range(config, "background", "blur_kernel", (3, 5)),
        },
        "frame": {
            "rotate_probability": _section_float(config, "frame", "rotate_probability", 0.35),
            "rotate_degrees": _range(config, "frame", "rotate_degrees", (-2.0, 2.0)),
        },
        "ball": {
            "scale": _range(config, "ball", "scale", (0.6, 1.8)),
            "stretch_x": _range(config, "ball", "stretch_x", (0.9, 1.1)),
            "stretch_y": _range(config, "ball", "stretch_y", (0.9, 1.1)),
            "brightness": _int_range(config, "ball", "brightness", (-35, 35)),
            "contrast": _range(config, "ball", "contrast", (0.8, 1.25)),
            "rotate_degrees": _range(config, "ball", "rotate_degrees", (-8, 8)),
            "motion_blur_probability": _section_float(config, "ball", "motion_blur_probability", 0.2),
            "motion_blur_kernel": _int_range(config, "ball", "motion_blur_kernel", (3, 9)),
            "alpha_threshold_for_bbox": _section_int(config, "ball", "alpha_threshold_for_bbox", 16),
            "min_visible_area_px": _section_int(config, "ball", "min_visible_area_px", 12),
            "avoid_existing_iou": _section_float(config, "ball", "avoid_existing_iou", 0.02),
        },
    }
    if resolved["output"]["count"] < 1:
        raise ValueError("output.count must be >= 1")
    if resolved["negative_augmentation"]["count"] < 0:
        raise ValueError("negative_augmentation.count must be >= 0")
    if not 0.0 <= resolved["split"]["val_ratio"] < 0.5:
        raise ValueError("split.val_ratio must be >= 0 and < 0.5")
    return resolved


def collect_backgrounds(resolved: dict[str, Any]) -> list[BackgroundRecord]:
    images_root = Path(resolved["inputs"]["images_root"]).resolve()
    labels_root = Path(resolved["inputs"]["labels_root"]).resolve()
    excluded = read_excluded_paths(Path(resolved["inputs"]["excluded_file"]))
    records: list[BackgroundRecord] = []
    cv2, _ = require_cv2_numpy()
    for rel_path in iter_image_paths(images_root):
        if rel_path in excluded:
            continue
        label_path = label_path_for_image(labels_root, rel_path)
        has_label_file = label_path.is_file()
        if resolved["selection"]["require_label_file_backgrounds"] and not has_label_file:
            continue
        label_text = label_path.read_text(encoding="utf-8") if has_label_file else ""
        label_lines = [line for line in label_text.splitlines() if line.strip()]
        if label_lines and not resolved["selection"]["allow_labeled_backgrounds"]:
            continue
        image_path = safe_relative_path(images_root, rel_path, IMAGE_SUFFIXES)
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            continue
        image_height, image_width = image.shape[:2]
        parsed_labels = read_yolo_labels(label_path)
        pixel_labels = [
            PixelLabel(label.class_id, yolo_to_pixel_box(label, image_width, image_height))
            for label in parsed_labels
        ]
        records.append(
            BackgroundRecord(
                image_rel_path=rel_path,
                image_path=image_path,
                label_path=label_path,
                has_label_file=has_label_file,
                labels=label_lines,
                boxes=[label.box for label in pixel_labels],
                is_negative=len(label_lines) == 0,
            )
        )
    return records


def collect_sprites(sprites_root: Path) -> list[SpriteRecord]:
    root = sprites_root.resolve()
    if not root.exists():
        return []
    sprites: list[SpriteRecord] = []
    for metadata_path in sorted(root.glob("*.json")):
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        sprite_file = metadata.get("files", {}).get("sprite")
        sprite_id = metadata.get("id")
        if not isinstance(sprite_file, str) or not isinstance(sprite_id, str):
            continue
        sprite_path = root / sprite_file
        if sprite_path.is_file():
            sprites.append(SpriteRecord(sprite_id=sprite_id, image_path=sprite_path, metadata_path=metadata_path))
    return sprites


def random_range(rng: random.Random, values: tuple[float, float]) -> float:
    return rng.uniform(values[0], values[1])


def random_int_range(rng: random.Random, values: tuple[int, int]) -> int:
    return rng.randint(values[0], values[1])


def odd_kernel(value: int) -> int:
    value = max(1, int(value))
    return value if value % 2 == 1 else value + 1


def adjust_brightness_contrast(image: Any, alpha: float, beta: int) -> Any:
    cv2, _ = require_cv2_numpy()
    return cv2.convertScaleAbs(image, alpha=float(alpha), beta=int(beta))


def augment_background_frame(background: Any, resolved: dict[str, Any], rng: random.Random) -> Any:
    cv2, _ = require_cv2_numpy()
    background = adjust_brightness_contrast(
        background,
        random_range(rng, resolved["background"]["contrast"]),
        random_int_range(rng, resolved["background"]["brightness"]),
    )
    if rng.random() < resolved["background"]["blur_probability"]:
        kernel = odd_kernel(random_int_range(rng, resolved["background"]["blur_kernel"]))
        background = cv2.GaussianBlur(background, (kernel, kernel), 0)
    return background


def maybe_rotate_frame(
    frame: Any,
    labels: list[PixelLabel],
    resolved: dict[str, Any],
    rng: random.Random,
) -> tuple[Any, list[PixelLabel], float]:
    degrees = 0.0
    if rng.random() < resolved["frame"]["rotate_probability"]:
        degrees = random_range(rng, resolved["frame"]["rotate_degrees"])
        if abs(degrees) > 1e-6:
            frame, labels = rotate_frame_and_labels(frame, labels, degrees)
    return frame, labels, degrees


def transform_sprite(sprite: Any, resolved: dict[str, Any], rng: random.Random, *, allow_rotation: bool) -> Any:
    cv2, _ = require_cv2_numpy()
    scale = random_range(rng, resolved["ball"]["scale"])
    stretch_x = random_range(rng, resolved["ball"]["stretch_x"])
    stretch_y = random_range(rng, resolved["ball"]["stretch_y"])
    new_width = max(1, int(round(sprite.shape[1] * scale * stretch_x)))
    new_height = max(1, int(round(sprite.shape[0] * scale * stretch_y)))
    sprite = cv2.resize(sprite, (new_width, new_height), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)

    bgr = sprite[:, :, :3]
    alpha = sprite[:, :, 3]
    bgr = adjust_brightness_contrast(
        bgr,
        random_range(rng, resolved["ball"]["contrast"]),
        random_int_range(rng, resolved["ball"]["brightness"]),
    )
    sprite = cv2.merge([bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2], alpha])

    if allow_rotation:
        degrees = random_range(rng, resolved["ball"]["rotate_degrees"])
        if abs(degrees) > 1e-6:
            sprite = rotate_rgba(sprite, degrees)

    if rng.random() < resolved["ball"]["motion_blur_probability"]:
        kernel_size = odd_kernel(random_int_range(rng, resolved["ball"]["motion_blur_kernel"]))
        sprite = motion_blur_rgba(sprite, kernel_size)
    return sprite


def labels_from_yolo_lines(label_lines: list[str], image_width: int, image_height: int) -> list[PixelLabel]:
    from .dataset import parse_yolo_label_line

    labels: list[PixelLabel] = []
    for line in label_lines:
        label = parse_yolo_label_line(line)
        if label is not None:
            labels.append(PixelLabel(label.class_id, yolo_to_pixel_box(label, image_width, image_height)))
    return labels


def rotate_rgba(image: Any, degrees: float) -> Any:
    cv2, _ = require_cv2_numpy()
    height, width = image.shape[:2]
    center = (width * 0.5, height * 0.5)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    cos_v = abs(matrix[0, 0])
    sin_v = abs(matrix[0, 1])
    new_width = int(height * sin_v + width * cos_v)
    new_height = int(height * cos_v + width * sin_v)
    matrix[0, 2] += new_width * 0.5 - center[0]
    matrix[1, 2] += new_height * 0.5 - center[1]
    return cv2.warpAffine(image, matrix, (new_width, new_height), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))


def motion_blur_rgba(image: Any, kernel_size: int) -> Any:
    cv2, np = require_cv2_numpy()
    kernel = np.zeros((kernel_size, kernel_size), dtype=np.float32)
    kernel[kernel_size // 2, :] = 1.0 / kernel_size
    return cv2.filter2D(image, -1, kernel)


def rotate_frame_and_labels(image: Any, labels: list[PixelLabel], degrees: float) -> tuple[Any, list[PixelLabel]]:
    cv2, _ = require_cv2_numpy()
    height, width = image.shape[:2]
    center = ((width - 1) * 0.5, (height - 1) * 0.5)
    matrix = cv2.getRotationMatrix2D(center, degrees, 1.0)
    rotated_image = cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )
    rotated_labels: list[PixelLabel] = []
    for label in labels:
        rotated_box = rotate_box(label.box, matrix, width, height)
        if rotated_box is not None:
            rotated_labels.append(PixelLabel(label.class_id, rotated_box))
    return rotated_image, rotated_labels


def rotate_box(box: PixelBox, matrix: Any, image_width: int, image_height: int) -> PixelBox | None:
    _, np = require_cv2_numpy()
    corners = np.array(
        [
            [box.x1, box.y1, 1.0],
            [box.x2, box.y1, 1.0],
            [box.x2, box.y2, 1.0],
            [box.x1, box.y2, 1.0],
        ],
        dtype=np.float32,
    )
    rotated = corners @ matrix.T
    x1 = max(0.0, float(rotated[:, 0].min()))
    y1 = max(0.0, float(rotated[:, 1].min()))
    x2 = min(float(image_width), float(rotated[:, 0].max()))
    y2 = min(float(image_height), float(rotated[:, 1].max()))
    if x2 <= x1 or y2 <= y1:
        return None
    return PixelBox(x1=x1, y1=y1, x2=x2, y2=y2)


def alpha_bbox(alpha: Any, threshold: int) -> PixelBox | None:
    _, np = require_cv2_numpy()
    points = np.argwhere(alpha > int(threshold))
    if points.size == 0:
        return None
    y1 = float(points[:, 0].min())
    y2 = float(points[:, 0].max() + 1)
    x1 = float(points[:, 1].min())
    x2 = float(points[:, 1].max() + 1)
    return PixelBox(x1=x1, y1=y1, x2=x2, y2=y2)


def box_iou(a: PixelBox, b: PixelBox) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = a.width * a.height + b.width * b.height - intersection
    return 0.0 if union <= 0 else intersection / union


def choose_paste_position(
    image_width: int,
    image_height: int,
    sprite_width: int,
    sprite_height: int,
    existing_boxes: list[PixelBox],
    rng: random.Random,
    avoid_iou: float,
) -> tuple[int, int] | None:
    if sprite_width > image_width or sprite_height > image_height:
        return None
    for _ in range(50):
        x = rng.randint(0, image_width - sprite_width)
        y = rng.randint(0, image_height - sprite_height)
        candidate = PixelBox(x, y, x + sprite_width, y + sprite_height)
        if all(box_iou(candidate, existing) <= avoid_iou for existing in existing_boxes):
            return x, y
    return rng.randint(0, image_width - sprite_width), rng.randint(0, image_height - sprite_height)


def paste_rgba(background: Any, sprite: Any, x: int, y: int, threshold: int) -> PixelBox | None:
    _, np = require_cv2_numpy()
    height, width = background.shape[:2]
    sprite_height, sprite_width = sprite.shape[:2]
    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + sprite_width)
    y2 = min(height, y + sprite_height)
    if x1 >= x2 or y1 >= y2:
        return None

    sx1 = x1 - x
    sy1 = y1 - y
    sx2 = sx1 + (x2 - x1)
    sy2 = sy1 + (y2 - y1)
    sprite_region = sprite[sy1:sy2, sx1:sx2]
    alpha = sprite_region[:, :, 3].astype(np.float32) / 255.0
    if np.count_nonzero(alpha * 255.0 > threshold) == 0:
        return None

    for channel in range(3):
        background[y1:y2, x1:x2, channel] = (
            sprite_region[:, :, channel].astype(np.float32) * alpha
            + background[y1:y2, x1:x2, channel].astype(np.float32) * (1.0 - alpha)
        ).astype(np.uint8)

    local_box = alpha_bbox(sprite_region[:, :, 3], threshold)
    if local_box is None:
        return None
    return PixelBox(
        x1=x1 + local_box.x1,
        y1=y1 + local_box.y1,
        x2=x1 + local_box.x2,
        y2=y1 + local_box.y2,
    )


def write_resolved_config(path: Path, resolved: dict[str, Any]) -> None:
    def render_value(value: Any) -> str:
        if isinstance(value, Path):
            return json.dumps(value.as_posix())
        if isinstance(value, str):
            return json.dumps(value)
        if isinstance(value, tuple):
            return "[" + ", ".join(render_value(item) for item in value) + "]"
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)

    lines: list[str] = []
    for section, values in resolved.items():
        lines.append(f"[{section}]")
        for key, value in values.items():
            lines.append(f"{key} = {render_value(value)}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_yaml(output_root: Path, train_txt: Path, val_txt: Path) -> None:
    text = "\n".join(
        [
            f"path: {output_root.resolve().as_posix()}",
            f"train: {train_txt.resolve().as_posix()}",
            f"val: {val_txt.resolve().as_posix()}",
            "nc: 1",
            "names:",
            "  0: tennis_ball",
            "",
        ]
    )
    (output_root / "data.yaml").write_text(text, encoding="utf-8")


def collect_labeled_original_images(resolved: dict[str, Any]) -> list[str]:
    images_root = Path(resolved["inputs"]["images_root"]).resolve()
    labels_root = Path(resolved["inputs"]["labels_root"]).resolve()
    excluded = read_excluded_paths(Path(resolved["inputs"]["excluded_file"]))
    images: list[str] = []
    for rel_path in iter_image_paths(images_root):
        if rel_path in excluded:
            continue
        label_path = label_path_for_image(labels_root, rel_path)
        if not label_path.is_file():
            continue
        image_path = safe_relative_path(images_root, rel_path, IMAGE_SUFFIXES)
        images.append(image_path.resolve().as_posix())
    return images


def write_augmented_sample(
    image: Any,
    labels: list[PixelLabel],
    image_path: Path,
    label_path: Path,
    *,
    jpeg_quality: int,
) -> None:
    cv2, _ = require_cv2_numpy()
    image_height, image_width = image.shape[:2]
    image_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.parent.mkdir(parents=True, exist_ok=True)
    params: list[int] = []
    if image_path.suffix.lower() in {".jpg", ".jpeg"}:
        params = [int(cv2.IMWRITE_JPEG_QUALITY), int(jpeg_quality)]
    if not cv2.imwrite(str(image_path), image, params):
        raise RuntimeError(f"could not write generated image: {image_path}")
    output_labels = [
        format_yolo_box(pixel_to_yolo_box(label.box, image_width, image_height, class_id=label.class_id))
        for label in labels
    ]
    label_path.write_text("\n".join(output_labels) + ("\n" if output_labels else ""), encoding="utf-8")


def split_images(images: list[str], val_ratio: float, seed: int) -> tuple[list[str], list[str]]:
    if not images or val_ratio <= 0.0 or len(images) < 2:
        return images, []
    shuffled = list(images)
    random.Random(seed).shuffle(shuffled)
    val_count = max(1, round(len(shuffled) * val_ratio))
    return shuffled[:-val_count], shuffled[-val_count:]


def copy_paste_augment(config_path: Path = DEFAULT_AUGMENT_CONFIG) -> AugmentationResult:
    cv2, _ = require_cv2_numpy()
    resolved = resolve_config(config_path)
    output_root = Path(resolved["output"]["root"]).resolve()
    if output_root.exists():
        shutil.rmtree(output_root)
    images_dir = output_root / "images"
    labels_dir = output_root / "labels"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    rng = random.Random(resolved["output"]["seed"])
    backgrounds = collect_backgrounds(resolved)
    if not backgrounds:
        raise RuntimeError("no usable background images found")
    sprites = collect_sprites(Path(resolved["inputs"]["sprites_root"]))
    if not sprites:
        raise RuntimeError("no approved sprites found")

    negative_backgrounds = [record for record in backgrounds if record.is_negative]
    preferred_backgrounds = negative_backgrounds if resolved["selection"]["prefer_negative_backgrounds"] and negative_backgrounds else backgrounds

    manifest_path = output_root / "manifest.jsonl"
    train_txt = output_root / "train.txt"
    val_txt = output_root / "val.txt"
    manifest_rows: list[dict[str, Any]] = []
    split_candidates: list[str] = []
    skipped = 0
    generated_positive = 0
    for index in range(resolved["output"]["count"]):
        background_record = rng.choice(preferred_backgrounds)
        background = cv2.imread(str(background_record.image_path), cv2.IMREAD_COLOR)
        if background is None:
            skipped += 1
            continue
        background = augment_background_frame(background, resolved, rng)

        image_height, image_width = background.shape[:2]
        output_pixel_labels = labels_from_yolo_lines(background_record.labels, image_width, image_height)
        existing_boxes = [label.box for label in output_pixel_labels]
        pasted: list[dict[str, Any]] = []
        paste_count = random_int_range(rng, resolved["selection"]["paste_per_image"])
        for _ in range(paste_count):
            sprite_record = rng.choice(sprites)
            sprite = cv2.imread(str(sprite_record.image_path), cv2.IMREAD_UNCHANGED)
            if sprite is None or sprite.ndim != 3 or sprite.shape[2] != 4:
                skipped += 1
                continue
            allow_rotation = background_record.is_negative
            sprite = transform_sprite(sprite, resolved, rng, allow_rotation=allow_rotation)
            sprite_height, sprite_width = sprite.shape[:2]
            position = choose_paste_position(
                image_width,
                image_height,
                sprite_width,
                sprite_height,
                existing_boxes,
                rng,
                resolved["ball"]["avoid_existing_iou"],
            )
            if position is None:
                skipped += 1
                continue
            bbox = paste_rgba(background, sprite, position[0], position[1], resolved["ball"]["alpha_threshold_for_bbox"])
            if bbox is None or bbox.width * bbox.height < resolved["ball"]["min_visible_area_px"]:
                skipped += 1
                continue
            existing_boxes.append(bbox)
            output_pixel_labels.append(PixelLabel(0, bbox))
            yolo_box = pixel_to_yolo_box(bbox, image_width, image_height, class_id=0)
            pasted.append(
                {
                    "sprite_id": sprite_record.sprite_id,
                    "x": position[0],
                    "y": position[1],
                    "bbox_px": {"x1": bbox.x1, "y1": bbox.y1, "x2": bbox.x2, "y2": bbox.y2},
                    "bbox_yolo": {
                        "class_id": yolo_box.class_id,
                        "x_center": yolo_box.x_center,
                        "y_center": yolo_box.y_center,
                        "width": yolo_box.width,
                        "height": yolo_box.height,
                    },
                }
            )

        if not pasted:
            skipped += 1
            continue

        background, output_pixel_labels, frame_rotation_degrees = maybe_rotate_frame(background, output_pixel_labels, resolved, rng)

        suffix = ".jpg" if resolved["output"]["image_format"] in {"jpg", "jpeg"} else ".png"
        output_stem = f"aug_{generated_positive:06d}"
        output_image = images_dir / f"{output_stem}{suffix}"
        output_label = labels_dir / f"{output_stem}.txt"
        write_augmented_sample(
            background,
            output_pixel_labels,
            output_image,
            output_label,
            jpeg_quality=resolved["output"]["jpeg_quality"],
        )
        split_candidates.append(output_image.resolve().as_posix())
        manifest_rows.append(
            {
                "kind": "copy_paste",
                "index": generated_positive,
                "source_background": background_record.image_rel_path,
                "source_label": background_record.label_path.as_posix(),
                "output_image": output_image.as_posix(),
                "output_label": output_label.as_posix(),
                "frame_rotation_degrees": frame_rotation_degrees,
                "pasted": pasted,
            }
        )
        generated_positive += 1

    generated_negative = 0
    requested_negatives = resolved["negative_augmentation"]["count"]
    if requested_negatives:
        if not negative_backgrounds:
            raise RuntimeError("negative_augmentation.count is set but no labeled negative backgrounds were found")
        suffix = ".jpg" if resolved["output"]["image_format"] in {"jpg", "jpeg"} else ".png"
        for _ in range(requested_negatives):
            background_record = rng.choice(negative_backgrounds)
            background = cv2.imread(str(background_record.image_path), cv2.IMREAD_COLOR)
            if background is None:
                skipped += 1
                continue
            background = augment_background_frame(background, resolved, rng)
            output_pixel_labels: list[PixelLabel] = []
            background, output_pixel_labels, frame_rotation_degrees = maybe_rotate_frame(background, output_pixel_labels, resolved, rng)
            output_stem = f"neg_{generated_negative:06d}"
            output_image = images_dir / f"{output_stem}{suffix}"
            output_label = labels_dir / f"{output_stem}.txt"
            write_augmented_sample(
                background,
                output_pixel_labels,
                output_image,
                output_label,
                jpeg_quality=resolved["output"]["jpeg_quality"],
            )
            split_candidates.append(output_image.resolve().as_posix())
            manifest_rows.append(
                {
                    "kind": "negative_augmentation",
                    "index": generated_negative,
                    "source_background": background_record.image_rel_path,
                    "source_label": background_record.label_path.as_posix(),
                    "output_image": output_image.as_posix(),
                    "output_label": output_label.as_posix(),
                    "frame_rotation_degrees": frame_rotation_degrees,
                    "pasted": [],
                }
            )
            generated_negative += 1

    original_images = collect_labeled_original_images(resolved) if resolved["originals"]["include"] else []
    train_images, val_images = split_images(
        split_candidates + original_images,
        resolved["split"]["val_ratio"],
        resolved["split"]["seed"],
    )

    manifest_path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in manifest_rows), encoding="utf-8")
    train_txt.write_text("\n".join(train_images) + ("\n" if train_images else ""), encoding="utf-8")
    val_txt.write_text("\n".join(val_images) + ("\n" if val_images else ""), encoding="utf-8")
    write_data_yaml(output_root, train_txt, val_txt)
    write_resolved_config(output_root / "config.resolved.toml", resolved)
    report_path = output_root / "report.md"
    generated_total = generated_positive + generated_negative
    report_path.write_text(
        "\n".join(
            [
                "# YOLO Copy-Paste Augmentation Report",
                "",
                f"- Generated images: {generated_total}",
                f"- Generated copy-paste positives: {generated_positive}",
                f"- Generated augmented negatives: {generated_negative}",
                f"- Original labeled images in split: {len(original_images)}",
                f"- Train images: {len(train_images)}",
                f"- Validation images: {len(val_images)}",
                f"- Skipped samples/events: {skipped}",
                f"- Backgrounds: {len(backgrounds)}",
                f"- Negative backgrounds: {len(negative_backgrounds)}",
                f"- Approved sprites: {len(sprites)}",
                f"- Require label file backgrounds: {resolved['selection']['require_label_file_backgrounds']}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return AugmentationResult(output_root=output_root, generated=generated_total, skipped=skipped, manifest=manifest_path, report=report_path)


def cmd_copy_paste(args: argparse.Namespace) -> int:
    try:
        result = copy_paste_augment(args.config)
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}")
        return 2
    print(f"generated={result.generated}")
    print(f"skipped={result.skipped}")
    print(f"output_root={result.output_root}")
    print(f"manifest={result.manifest}")
    print(f"report={result.report}")
    return 0


def add_augment_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    augment = subparsers.add_parser("augment", help="生成 YOLO 训练数据增强数据集。", **parser_kwargs)
    augment_subparsers = augment.add_subparsers(dest="augment_command", required=True)
    copy_paste = augment_subparsers.add_parser("copy-paste", help="使用审核过的球 sprite 做 copy-paste 增强。", **parser_kwargs)
    copy_paste.add_argument("--config", type=Path, default=DEFAULT_AUGMENT_CONFIG, help="共享增强配置 TOML")
    copy_paste.set_defaults(func=cmd_copy_paste)
