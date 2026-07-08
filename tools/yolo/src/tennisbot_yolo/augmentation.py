from __future__ import annotations

import argparse
from collections import Counter
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
DEFAULT_FINAL_RAW_MANIFEST = DEFAULT_RUNS_ROOT / "final_raw_benchmark_v1_20260708" / "manifest.jsonl"
DEFAULT_FINAL_TRAINSET_OUTPUT = DEFAULT_RUNS_ROOT / "final_trainpool_roi_full_20260708"


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


@dataclass(frozen=True)
class FinalManifestRecord:
    image: str
    label: str
    split: str
    dataset: str
    session: str
    target_bucket: str
    positive: bool
    box_count: int


@dataclass(frozen=True)
class FinalTrainsetResult:
    output_root: Path
    images: int
    train_images: int
    val_images: int
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


def make_tiny_ball_sprite(
    source_image: Any,
    label: PixelLabel,
    *,
    target_max_dim: float,
    rng: random.Random,
) -> Any | None:
    cv2, np = require_cv2_numpy()
    if label.box.width <= 0.0 or label.box.height <= 0.0 or target_max_dim <= 0.0:
        return None

    image_height, image_width = source_image.shape[:2]
    pad = max(2.0, max(label.box.width, label.box.height) * 0.35)
    crop_x1 = max(0, int(label.box.x1 - pad))
    crop_y1 = max(0, int(label.box.y1 - pad))
    crop_x2 = min(image_width, int(label.box.x2 + pad) + 1)
    crop_y2 = min(image_height, int(label.box.y2 + pad) + 1)
    if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
        return None

    patch = source_image[crop_y1:crop_y2, crop_x1:crop_x2]
    local_box = PixelBox(
        x1=label.box.x1 - crop_x1,
        y1=label.box.y1 - crop_y1,
        x2=label.box.x2 - crop_x1,
        y2=label.box.y2 - crop_y1,
    )
    scale = target_max_dim / max(local_box.width, local_box.height)
    sprite_width = max(1, int(round(patch.shape[1] * scale)))
    sprite_height = max(1, int(round(patch.shape[0] * scale)))
    if sprite_width < 2 or sprite_height < 2:
        return None

    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    bgr = cv2.resize(patch, (sprite_width, sprite_height), interpolation=interpolation)
    bgr = adjust_brightness_contrast(bgr, rng.uniform(0.80, 1.25), rng.randint(-35, 35))

    scaled_box = PixelBox(
        x1=local_box.x1 * scale,
        y1=local_box.y1 * scale,
        x2=local_box.x2 * scale,
        y2=local_box.y2 * scale,
    )
    alpha = np.zeros((sprite_height, sprite_width), dtype=np.uint8)
    center = (int(round(scaled_box.x_center)), int(round(scaled_box.y_center)))
    axes = (
        max(1, int(round(scaled_box.width * 0.5))),
        max(1, int(round(scaled_box.height * 0.5))),
    )
    cv2.ellipse(alpha, center, axes, 0.0, 0.0, 360.0, 255, -1)
    if max(axes) >= 2:
        alpha = cv2.GaussianBlur(alpha, (3, 3), 0)
    sprite = cv2.merge([bgr[:, :, 0], bgr[:, :, 1], bgr[:, :, 2], alpha])

    for _ in range(3):
        visible_box = alpha_bbox(sprite[:, :, 3], threshold=16)
        if visible_box is None:
            return None
        visible_max_dim = max(visible_box.width, visible_box.height)
        if visible_max_dim <= 0.0:
            return None
        correction_scale = target_max_dim / visible_max_dim
        if abs(correction_scale - 1.0) <= 0.05:
            break
        corrected_width = max(1, int(round(sprite.shape[1] * correction_scale)))
        corrected_height = max(1, int(round(sprite.shape[0] * correction_scale)))
        corrected_interpolation = cv2.INTER_AREA if correction_scale < 1.0 else cv2.INTER_LINEAR
        sprite = cv2.resize(sprite, (corrected_width, corrected_height), interpolation=corrected_interpolation)
    return sprite


def choose_tiny_paste_position(
    image_width: int,
    image_height: int,
    sprite_width: int,
    sprite_height: int,
    rng: random.Random,
) -> tuple[int, int] | None:
    if sprite_width > image_width or sprite_height > image_height:
        return None
    margin = 24
    min_x = margin if image_width - sprite_width >= margin * 2 else 0
    min_y = margin if image_height - sprite_height >= margin * 2 else 0
    max_x = image_width - sprite_width - min_x
    max_y = image_height - sprite_height - min_y
    if max_x < min_x:
        min_x, max_x = 0, image_width - sprite_width
    if max_y < min_y:
        min_y, max_y = 0, image_height - sprite_height
    return rng.randint(min_x, max_x), rng.randint(min_y, max_y)


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


def repo_input_path(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def load_final_manifest(path: Path) -> list[FinalManifestRecord]:
    if not path.is_file():
        raise FileNotFoundError(f"final raw manifest not found: {path}")
    records: list[FinalManifestRecord] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            records.append(
                FinalManifestRecord(
                    image=str(row["image"]),
                    label=str(row["label"]),
                    split=str(row["split"]),
                    dataset=str(row["dataset"]),
                    session=str(row["session"]),
                    target_bucket=str(row["target_bucket"]),
                    positive=bool(row["positive"]),
                    box_count=int(row["box_count"]),
                )
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid manifest row {line_number}: {path}") from exc
    return records


def final_trainpool_records(records: list[FinalManifestRecord]) -> list[FinalManifestRecord]:
    return [record for record in records if record.split == "train_pool"]


def resize_image_and_labels(image: Any, labels: list[PixelLabel], width: int, height: int) -> tuple[Any, list[PixelLabel]]:
    cv2, _ = require_cv2_numpy()
    src_height, src_width = image.shape[:2]
    if src_width == width and src_height == height:
        return image.copy(), labels
    resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_AREA)
    scale_x = width / src_width
    scale_y = height / src_height
    resized_labels = [
        PixelLabel(
            label.class_id,
            PixelBox(
                x1=label.box.x1 * scale_x,
                y1=label.box.y1 * scale_y,
                x2=label.box.x2 * scale_x,
                y2=label.box.y2 * scale_y,
            ),
        )
        for label in labels
    ]
    return resized, resized_labels


def crop_image_and_labels(
    image: Any,
    labels: list[PixelLabel],
    x1: int,
    y1: int,
    width: int,
    height: int,
) -> tuple[Any, list[PixelLabel]]:
    crop = image[y1 : y1 + height, x1 : x1 + width].copy()
    crop_labels: list[PixelLabel] = []
    for label in labels:
        if not (x1 <= label.box.x_center <= x1 + width and y1 <= label.box.y_center <= y1 + height):
            continue
        clipped = PixelBox(
            x1=max(0.0, label.box.x1 - x1),
            y1=max(0.0, label.box.y1 - y1),
            x2=min(float(width), label.box.x2 - x1),
            y2=min(float(height), label.box.y2 - y1),
        )
        if clipped.width > 0.0 and clipped.height > 0.0:
            crop_labels.append(PixelLabel(label.class_id, clipped))
    return crop, crop_labels


def roi_window_for_anchor(
    box: PixelBox,
    image_width: int,
    image_height: int,
    roi_width: int,
    roi_height: int,
    anchor_x: float,
    anchor_y: float,
) -> tuple[int, int, int, int]:
    roi_width = min(roi_width, image_width)
    roi_height = min(roi_height, image_height)
    x1 = int(round(box.x_center - anchor_x * roi_width))
    y1 = int(round(box.y_center - anchor_y * roi_height))
    x1 = min(max(0, x1), image_width - roi_width)
    y1 = min(max(0, y1), image_height - roi_height)
    return x1, y1, roi_width, roi_height


def random_negative_window(
    image_width: int,
    image_height: int,
    roi_width: int,
    roi_height: int,
    rng: random.Random,
) -> tuple[int, int, int, int]:
    roi_width = min(roi_width, image_width)
    roi_height = min(roi_height, image_height)
    x1 = rng.randint(0, image_width - roi_width) if image_width > roi_width else 0
    y1 = rng.randint(0, image_height - roi_height) if image_height > roi_height else 0
    return x1, y1, roi_width, roi_height


def maybe_flip_horizontal(image: Any, labels: list[PixelLabel], probability: float, rng: random.Random) -> tuple[Any, list[PixelLabel], bool]:
    cv2, _ = require_cv2_numpy()
    if rng.random() >= probability:
        return image, labels, False
    width = image.shape[1]
    flipped = cv2.flip(image, 1)
    flipped_labels = [
        PixelLabel(
            label.class_id,
            PixelBox(
                x1=width - label.box.x2,
                y1=label.box.y1,
                x2=width - label.box.x1,
                y2=label.box.y2,
            ),
        )
        for label in labels
    ]
    return flipped, flipped_labels, True


def apply_final_trainset_augmentation(
    image: Any,
    labels: list[PixelLabel],
    rng: random.Random,
    *,
    enable_geometric: bool,
) -> tuple[Any, list[PixelLabel], dict[str, Any]]:
    cv2, np = require_cv2_numpy()
    alpha = rng.uniform(0.65, 1.45)
    beta = rng.randint(-70, 70)
    image = adjust_brightness_contrast(image, alpha, beta)

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
    saturation_scale = rng.uniform(0.60, 1.55)
    value_scale = rng.uniform(0.70, 1.40)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * saturation_scale, 0, 255)
    hsv[:, :, 2] = np.clip(hsv[:, :, 2] * value_scale, 0, 255)
    image = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

    flipped = False
    rotation_degrees = 0.0
    if enable_geometric:
        image, labels, flipped = maybe_flip_horizontal(image, labels, 0.25, rng)
        if rng.random() < 0.35:
            rotation_degrees = rng.uniform(-2.0, 2.0)
            image, labels = rotate_frame_and_labels(image, labels, rotation_degrees)

    blur_kernel = 0
    if rng.random() < 0.12:
        blur_kernel = odd_kernel(rng.randint(3, 5))
        image = cv2.GaussianBlur(image, (blur_kernel, blur_kernel), 0)

    noise_sigma = 0.0
    if rng.random() < 0.20:
        noise_sigma = rng.uniform(2.0, 8.0)
        noise_array = np.random.default_rng(rng.randint(0, 2**31 - 1)).normal(0.0, noise_sigma, image.shape)
        image = np.clip(image.astype(np.float32) + noise_array, 0, 255).astype(np.uint8)

    return image, labels, {
        "alpha": alpha,
        "beta": beta,
        "saturation_scale": saturation_scale,
        "value_scale": value_scale,
        "flipped": flipped,
        "rotation_degrees": rotation_degrees,
        "blur_kernel": blur_kernel,
        "noise_sigma": noise_sigma,
    }


def labels_for_record(record: FinalManifestRecord, image_width: int, image_height: int) -> list[PixelLabel]:
    labels = read_yolo_labels(repo_input_path(record.label))
    return [PixelLabel(label.class_id, yolo_to_pixel_box(label, image_width, image_height)) for label in labels]


def source_split_map(records: list[FinalManifestRecord], val_ratio: float, seed: int) -> dict[str, str]:
    sources = sorted({record.image for record in records})
    if not sources:
        return {}
    rng = random.Random(seed)
    shuffled = list(sources)
    rng.shuffle(shuffled)
    val_count = max(1, round(len(shuffled) * val_ratio)) if len(shuffled) > 1 and val_ratio > 0.0 else 0
    val_sources = set(shuffled[:val_count])
    return {source: ("val" if source in val_sources else "train") for source in sources}


def write_final_dataset_sample(
    *,
    image: Any,
    labels: list[PixelLabel],
    output_images_dir: Path,
    output_labels_dir: Path,
    stem: str,
    jpeg_quality: int,
) -> tuple[Path, Path]:
    image_path = output_images_dir / f"{stem}.jpg"
    label_path = output_labels_dir / f"{stem}.txt"
    write_augmented_sample(image, labels, image_path, label_path, jpeg_quality=jpeg_quality)
    return image_path, label_path


def final_positive_weight(record: FinalManifestRecord) -> float:
    bucket_weight = {"small": 7.0, "medium": 4.0, "large": 1.0}.get(record.target_bucket, 1.0)
    dataset_weight = 1.25 if record.dataset == "fixed_exposure" else 0.75
    return bucket_weight * dataset_weight


def final_trainset_dry_summary(
    records: list[FinalManifestRecord],
    *,
    include_full_frame: bool,
    roi_positive_count: int,
    negative_crop_count: int,
    tiny_positive_count: int,
    tiny_min_dim: float,
    tiny_max_dim: float,
    val_ratio: float,
    seed: int,
) -> dict[str, Any]:
    train_pool = final_trainpool_records(records)
    split_map = source_split_map(train_pool, val_ratio, seed)
    fixed_positive_records = [record for record in train_pool if record.positive and record.dataset == "fixed_exposure"]
    fixed_negative_records = [record for record in train_pool if not record.positive and record.dataset == "fixed_exposure"]
    return {
        "train_pool_records": len(train_pool),
        "source_images": len(split_map),
        "planned_full_frame": len(train_pool) if include_full_frame else 0,
        "planned_roi_positive": roi_positive_count,
        "planned_negative_crops": negative_crop_count,
        "planned_tiny_positive": tiny_positive_count,
        "tiny_target_max_dim_range": [tiny_min_dim, tiny_max_dim],
        "tiny_fixed_positive_candidates": len(fixed_positive_records),
        "tiny_fixed_negative_candidates": len(fixed_negative_records),
        "dataset_counts": dict(sorted(Counter(record.dataset for record in train_pool).items())),
        "bucket_counts": dict(sorted(Counter(record.target_bucket for record in train_pool).items())),
        "session_counts": dict(sorted(Counter(record.session for record in train_pool).items())),
        "source_split_counts": dict(sorted(Counter(split_map.values()).items())),
    }


def build_final_trainset(
    *,
    manifest_path: Path,
    output_root: Path,
    seed: int,
    include_full_frame: bool,
    full_width: int,
    full_height: int,
    roi_width: int,
    roi_height: int,
    roi_positive_count: int,
    negative_crop_count: int,
    tiny_positive_count: int,
    tiny_min_dim: float,
    tiny_max_dim: float,
    val_ratio: float,
    jpeg_quality: int,
    dry_run: bool = False,
) -> FinalTrainsetResult | dict[str, Any]:
    records = final_trainpool_records(load_final_manifest(manifest_path))
    if not records:
        raise RuntimeError("final manifest does not contain train_pool records")
    if full_width <= 0 or full_height <= 0 or roi_width <= 0 or roi_height <= 0:
        raise ValueError("full and ROI dimensions must be positive")
    if roi_positive_count < 0 or negative_crop_count < 0:
        raise ValueError("generated sample counts must be non-negative")
    if tiny_positive_count < 0:
        raise ValueError("tiny_positive_count must be non-negative")
    if tiny_min_dim <= 0.0 or tiny_max_dim <= 0.0 or tiny_min_dim > tiny_max_dim:
        raise ValueError("tiny target max-dim range must be positive and ordered")
    if not 0.0 <= val_ratio < 0.5:
        raise ValueError("val_ratio must be >= 0 and < 0.5")

    if dry_run:
        return final_trainset_dry_summary(
            records,
            include_full_frame=include_full_frame,
            roi_positive_count=roi_positive_count,
            negative_crop_count=negative_crop_count,
            tiny_positive_count=tiny_positive_count,
            tiny_min_dim=tiny_min_dim,
            tiny_max_dim=tiny_max_dim,
            val_ratio=val_ratio,
            seed=seed,
        )

    cv2, _ = require_cv2_numpy()
    if output_root.exists():
        shutil.rmtree(output_root)
    images_dir = output_root / "images" / "trainset"
    labels_dir = output_root / "labels" / "trainset"
    images_dir.mkdir(parents=True)
    labels_dir.mkdir(parents=True)

    rng = random.Random(seed)
    split_map = source_split_map(records, val_ratio, seed)
    train_images: list[str] = []
    val_images: list[str] = []
    manifest_rows: list[dict[str, Any]] = []
    kind_counts: Counter[str] = Counter()
    skipped = 0
    skipped_tiny = 0

    def load_record(record: FinalManifestRecord) -> tuple[Any, list[PixelLabel]]:
        image_path = repo_input_path(record.image)
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise RuntimeError(f"failed to read image: {image_path}")
        height, width = image.shape[:2]
        return image, labels_for_record(record, width, height)

    def add_sample(
        *,
        record: FinalManifestRecord,
        kind: str,
        index: int,
        image: Any,
        labels: list[PixelLabel],
        extra: dict[str, Any],
    ) -> None:
        stem = f"{kind}_{index:06d}"
        output_image, output_label = write_final_dataset_sample(
            image=image,
            labels=labels,
            output_images_dir=images_dir,
            output_labels_dir=labels_dir,
            stem=stem,
            jpeg_quality=jpeg_quality,
        )
        split = split_map.get(record.image, "train")
        target_list = val_images if split == "val" else train_images
        target_list.append(output_image.resolve().as_posix())
        kind_counts[kind] += 1
        manifest_rows.append(
            {
                "kind": kind,
                "index": index,
                "split": split,
                "source_image": record.image,
                "source_label": record.label,
                "source_dataset": record.dataset,
                "source_session": record.session,
                "source_bucket": record.target_bucket,
                "output_image": output_image.as_posix(),
                "output_label": output_label.as_posix(),
                "label_count": len(labels),
                **extra,
            }
        )

    if include_full_frame:
        for index, record in enumerate(records):
            image, labels = load_record(record)
            image, labels = resize_image_and_labels(image, labels, full_width, full_height)
            add_sample(
                record=record,
                kind="full1080",
                index=index,
                image=image,
                labels=labels,
                extra={"full_width": full_width, "full_height": full_height},
            )

    positive_records = [record for record in records if record.positive]
    if roi_positive_count and not positive_records:
        raise RuntimeError("roi_positive_count is set but train_pool has no positive records")
    positive_weights = [final_positive_weight(record) for record in positive_records]
    anchor_grid = (0.18, 0.32, 0.50, 0.68, 0.82)
    for index in range(roi_positive_count):
        record = rng.choices(positive_records, weights=positive_weights, k=1)[0]
        image, labels = load_record(record)
        if not labels:
            skipped += 1
            continue
        anchor_label = max(labels, key=lambda label: label.box.width * label.box.height)
        anchor_x = rng.choice(anchor_grid)
        anchor_y = rng.choice(anchor_grid)
        image_height, image_width = image.shape[:2]
        crop_x, crop_y, crop_w, crop_h = roi_window_for_anchor(
            anchor_label.box,
            image_width,
            image_height,
            roi_width,
            roi_height,
            anchor_x,
            anchor_y,
        )
        crop, crop_labels = crop_image_and_labels(image, labels, crop_x, crop_y, crop_w, crop_h)
        if not crop_labels:
            skipped += 1
            continue
        crop, crop_labels, aug_meta = apply_final_trainset_augmentation(crop, crop_labels, rng, enable_geometric=True)
        add_sample(
            record=record,
            kind="roi_positive",
            index=index,
            image=crop,
            labels=crop_labels,
            extra={
                "crop": {"x": crop_x, "y": crop_y, "width": crop_w, "height": crop_h},
                "anchor": {"x": anchor_x, "y": anchor_y},
                "augmentation": aug_meta,
            },
        )

    negative_records = [record for record in records if not record.positive]
    if negative_crop_count and not negative_records:
        raise RuntimeError("negative_crop_count is set but train_pool has no negative records")
    for index in range(negative_crop_count):
        record = rng.choice(negative_records)
        image, _ = load_record(record)
        image_height, image_width = image.shape[:2]
        crop_x, crop_y, crop_w, crop_h = random_negative_window(image_width, image_height, roi_width, roi_height, rng)
        crop, crop_labels = crop_image_and_labels(image, [], crop_x, crop_y, crop_w, crop_h)
        crop, crop_labels, aug_meta = apply_final_trainset_augmentation(crop, crop_labels, rng, enable_geometric=True)
        add_sample(
            record=record,
            kind="roi_negative",
            index=index,
            image=crop,
            labels=crop_labels,
            extra={
                "crop": {"x": crop_x, "y": crop_y, "width": crop_w, "height": crop_h},
                "augmentation": aug_meta,
            },
        )

    if tiny_positive_count:
        fixed_positive_records = [record for record in positive_records if record.dataset == "fixed_exposure"]
        tiny_positive_records = fixed_positive_records if fixed_positive_records else positive_records
        fixed_negative_records = [record for record in negative_records if record.dataset == "fixed_exposure"]
        tiny_background_records = fixed_negative_records if fixed_negative_records else negative_records
        if not tiny_positive_records:
            raise RuntimeError("tiny_positive_count is set but train_pool has no positive records")
        if not tiny_background_records:
            raise RuntimeError("tiny_positive_count is set but train_pool has no negative backgrounds")

        positive_by_split: dict[str, list[FinalManifestRecord]] = {"train": [], "val": []}
        for record in tiny_positive_records:
            positive_by_split.setdefault(split_map.get(record.image, "train"), []).append(record)
        eligible_background_records = [
            record
            for record in tiny_background_records
            if positive_by_split.get(split_map.get(record.image, "train"))
        ]
        if not eligible_background_records:
            raise RuntimeError("tiny_positive_count is set but no negative backgrounds share a split with positive records")

        for index in range(tiny_positive_count):
            background_record = rng.choice(eligible_background_records)
            split = split_map.get(background_record.image, "train")
            split_positive_records = positive_by_split[split]
            source_record = rng.choices(
                split_positive_records,
                weights=[final_positive_weight(record) for record in split_positive_records],
                k=1,
            )[0]
            source_image, source_labels = load_record(source_record)
            if not source_labels:
                skipped_tiny += 1
                continue
            source_label = rng.choice(source_labels)
            target_max_dim = rng.uniform(tiny_min_dim, tiny_max_dim)
            sprite = make_tiny_ball_sprite(source_image, source_label, target_max_dim=target_max_dim, rng=rng)
            if sprite is None:
                skipped_tiny += 1
                continue

            background_image, _ = load_record(background_record)
            image_height, image_width = background_image.shape[:2]
            crop_x, crop_y, crop_w, crop_h = random_negative_window(image_width, image_height, roi_width, roi_height, rng)
            crop, _ = crop_image_and_labels(background_image, [], crop_x, crop_y, crop_w, crop_h)
            position = choose_tiny_paste_position(crop_w, crop_h, sprite.shape[1], sprite.shape[0], rng)
            if position is None:
                skipped_tiny += 1
                continue
            paste_x, paste_y = position
            pasted_box = paste_rgba(crop, sprite, paste_x, paste_y, threshold=16)
            if pasted_box is None:
                skipped_tiny += 1
                continue

            tiny_labels = [PixelLabel(source_label.class_id, pasted_box)]
            crop, tiny_labels, aug_meta = apply_final_trainset_augmentation(crop, tiny_labels, rng, enable_geometric=False)
            if not tiny_labels:
                skipped_tiny += 1
                continue
            add_sample(
                record=background_record,
                kind="tiny_positive",
                index=index,
                image=crop,
                labels=tiny_labels,
                extra={
                    "crop": {"x": crop_x, "y": crop_y, "width": crop_w, "height": crop_h},
                    "sprite_source_image": source_record.image,
                    "sprite_source_label": source_record.label,
                    "sprite_source_bucket": source_record.target_bucket,
                    "target_max_dim_px": target_max_dim,
                    "pasted_box": {
                        "x1": pasted_box.x1,
                        "y1": pasted_box.y1,
                        "x2": pasted_box.x2,
                        "y2": pasted_box.y2,
                    },
                    "augmentation": aug_meta,
                },
            )

    train_txt = output_root / "train.txt"
    val_txt = output_root / "val.txt"
    manifest_out = output_root / "manifest.jsonl"
    report_path = output_root / "report.md"
    train_txt.write_text("\n".join(train_images) + ("\n" if train_images else ""), encoding="utf-8")
    val_txt.write_text("\n".join(val_images) + ("\n" if val_images else ""), encoding="utf-8")
    manifest_out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in manifest_rows), encoding="utf-8")
    write_data_yaml(output_root, train_txt, val_txt)
    report_lines = [
        "# YOLO Final Train-Pool Dataset Report",
        "",
        f"- Source manifest: `{manifest_path}`",
        f"- Output root: `{output_root}`",
        f"- Seed: `{seed}`",
        f"- Train-pool source images: `{len(records)}`",
        f"- Generated images: `{len(manifest_rows)}`",
        f"- Train images: `{len(train_images)}`",
        f"- Val images: `{len(val_images)}`",
        f"- Skipped positive crops: `{skipped}`",
        f"- Skipped tiny copy-paste crops: `{skipped_tiny}`",
        f"- Kind counts: `{json.dumps(dict(sorted(kind_counts.items())), sort_keys=True)}`",
        f"- Source bucket counts: `{json.dumps(dict(sorted(Counter(record.target_bucket for record in records).items())), sort_keys=True)}`",
        f"- Source dataset counts: `{json.dumps(dict(sorted(Counter(record.dataset for record in records).items())), sort_keys=True)}`",
        f"- Tiny target max-dim range: `{tiny_min_dim:.2f}-{tiny_max_dim:.2f}px`",
        "",
        "## Policy",
        "",
        "- Only `train_pool` rows from the final raw benchmark manifest are used.",
        "- The frozen `benchmark` split is not read for image generation.",
        "- Train/val assignment is grouped by source image, so derived samples from one raw image cannot cross train/val.",
        "- ROI crops are clamped inside the source image; no padding or synthetic border fill is used.",
        "- Tiny copy-paste samples use only train_pool positives and train_pool negative backgrounds, with sprite source split matched to the background split.",
        "- Traditional augmentation uses brightness, contrast, saturation, value, optional horizontal flip, small rotation, blur, and Gaussian noise.",
        "",
    ]
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return FinalTrainsetResult(
        output_root=output_root,
        images=len(manifest_rows),
        train_images=len(train_images),
        val_images=len(val_images),
        manifest=manifest_out,
        report=report_path,
    )


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


def cmd_build_final_trainset(args: argparse.Namespace) -> int:
    try:
        result = build_final_trainset(
            manifest_path=args.manifest,
            output_root=args.output_root,
            seed=args.seed,
            include_full_frame=not args.no_full_frame,
            full_width=args.full_width,
            full_height=args.full_height,
            roi_width=args.roi_width,
            roi_height=args.roi_height,
            roi_positive_count=args.roi_positive_count,
            negative_crop_count=args.negative_crop_count,
            tiny_positive_count=args.tiny_positive_count,
            tiny_min_dim=args.tiny_min_dim,
            tiny_max_dim=args.tiny_max_dim,
            val_ratio=args.val_ratio,
            jpeg_quality=args.jpeg_quality,
            dry_run=args.dry_run,
        )
    except (RuntimeError, ValueError, FileNotFoundError) as exc:
        print(f"error: {exc}")
        return 2
    if args.dry_run:
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    assert isinstance(result, FinalTrainsetResult)
    print(f"images={result.images}")
    print(f"train_images={result.train_images}")
    print(f"val_images={result.val_images}")
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

    final_trainset = augment_subparsers.add_parser(
        "build-final-trainset",
        help="只从 final benchmark train_pool 生成 full-frame/ROI 训练集。",
        **parser_kwargs,
    )
    final_trainset.add_argument("--manifest", type=Path, default=DEFAULT_FINAL_RAW_MANIFEST, help="final raw benchmark manifest")
    final_trainset.add_argument("--output-root", type=Path, default=DEFAULT_FINAL_TRAINSET_OUTPUT, help="训练集输出目录")
    final_trainset.add_argument("--seed", type=int, default=20260708, help="随机种子")
    final_trainset.add_argument("--no-full-frame", action="store_true", help="不加入 1920x1080 full-frame 样本")
    final_trainset.add_argument("--full-width", type=int, default=1920, help="full-frame 输出宽度")
    final_trainset.add_argument("--full-height", type=int, default=1080, help="full-frame 输出高度")
    final_trainset.add_argument("--roi-width", type=int, default=1024, help="ROI crop 宽度")
    final_trainset.add_argument("--roi-height", type=int, default=576, help="ROI crop 高度")
    final_trainset.add_argument("--roi-positive-count", type=int, default=5000, help="生成多少个正样本 ROI crop")
    final_trainset.add_argument("--negative-crop-count", type=int, default=1500, help="生成多少个 empty hard-negative ROI crop")
    final_trainset.add_argument("--tiny-positive-count", type=int, default=0, help="生成多少个 4-8px tiny ball copy-paste ROI crop")
    final_trainset.add_argument("--tiny-min-dim", type=float, default=4.0, help="tiny copy-paste 目标最大边最小像素")
    final_trainset.add_argument("--tiny-max-dim", type=float, default=8.0, help="tiny copy-paste 目标最大边最大像素")
    final_trainset.add_argument("--val-ratio", type=float, default=0.10, help="按 source image 分组的 val 比例")
    final_trainset.add_argument("--jpeg-quality", type=int, default=92, help="输出 JPEG 质量")
    final_trainset.add_argument("--dry-run", action="store_true", help="只打印 train_pool 计数和计划，不读图片或写文件")
    final_trainset.set_defaults(func=cmd_build_final_trainset)
