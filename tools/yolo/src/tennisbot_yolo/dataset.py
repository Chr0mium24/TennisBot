from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".webp"}


@dataclass(frozen=True)
class YoloBox:
    class_id: int
    x_center: float
    y_center: float
    width: float
    height: float


@dataclass(frozen=True)
class PixelBox:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def x_center(self) -> float:
        return 0.5 * (self.x1 + self.x2)

    @property
    def y_center(self) -> float:
        return 0.5 * (self.y1 + self.y2)


def iter_image_paths(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and not path.is_symlink() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def normalize_dataset_rel_path(path: str) -> str:
    if path.startswith(("/", "\\")):
        raise ValueError("path must be relative")
    parts = PurePosixPath(path).parts
    if not parts or any(part in {"", ".", ".."} or "\x00" in part for part in parts):
        raise ValueError("path contains an unsafe segment")
    return PurePosixPath(*parts).as_posix()


def safe_relative_path(root: Path, raw_path: str, allowed_suffixes: set[str] | None = None) -> Path:
    normalized = normalize_dataset_rel_path(raw_path)
    root = root.resolve()
    candidate = (root / Path(*PurePosixPath(normalized).parts)).resolve()
    if candidate != root and root not in candidate.parents:
        raise ValueError("path escapes the root directory")
    if allowed_suffixes and candidate.suffix.lower() not in {suffix.lower() for suffix in allowed_suffixes}:
        raise ValueError(f"unsupported file suffix: {candidate.suffix}")
    return candidate


def label_path_for_image(labels_root: Path, image_path: str) -> Path:
    rel_path = PurePosixPath(normalize_dataset_rel_path(image_path)).with_suffix(".txt")
    return labels_root / Path(*rel_path.parts)


def read_excluded_paths(path: Path | None) -> set[str]:
    if path is None or not path.is_file():
        return set()
    excluded: set[str] = set()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        excluded.add(normalize_dataset_rel_path(line))
    return excluded


def parse_yolo_label_line(line: str) -> YoloBox | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    parts = stripped.split()
    if len(parts) != 5:
        raise ValueError(f"YOLO label line must have 5 fields: {line!r}")
    class_id = int(parts[0])
    values = [float(value) for value in parts[1:]]
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError(f"YOLO label values must be normalized to [0, 1]: {line!r}")
    return YoloBox(class_id=class_id, x_center=values[0], y_center=values[1], width=values[2], height=values[3])


def read_yolo_labels(path: Path) -> list[YoloBox]:
    if not path.is_file():
        return []
    labels: list[YoloBox] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        box = parse_yolo_label_line(line)
        if box is not None:
            labels.append(box)
    return labels


def yolo_to_pixel_box(box: YoloBox, image_width: int, image_height: int) -> PixelBox:
    x1 = (box.x_center - box.width * 0.5) * image_width
    y1 = (box.y_center - box.height * 0.5) * image_height
    x2 = (box.x_center + box.width * 0.5) * image_width
    y2 = (box.y_center + box.height * 0.5) * image_height
    return PixelBox(
        x1=max(0.0, min(float(image_width), x1)),
        y1=max(0.0, min(float(image_height), y1)),
        x2=max(0.0, min(float(image_width), x2)),
        y2=max(0.0, min(float(image_height), y2)),
    )


def pixel_to_yolo_box(box: PixelBox, image_width: int, image_height: int, class_id: int = 0) -> YoloBox:
    if image_width <= 0 or image_height <= 0:
        raise ValueError("image dimensions must be positive")
    return YoloBox(
        class_id=class_id,
        x_center=box.x_center / image_width,
        y_center=box.y_center / image_height,
        width=box.width / image_width,
        height=box.height / image_height,
    )


def format_yolo_box(box: YoloBox) -> str:
    return (
        f"{box.class_id} "
        f"{box.x_center:.6f} {box.y_center:.6f} "
        f"{box.width:.6f} {box.height:.6f}"
    )
