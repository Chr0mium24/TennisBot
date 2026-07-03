from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennisbot_yolo.augmentation import PixelLabel, copy_paste_augment, rotate_frame_and_labels, transform_sprite
from tennisbot_yolo.dataset import parse_yolo_label_line, yolo_to_pixel_box
from tennisbot_yolo.sprites import copy_reviewed_sprite, extract_sprites, load_sprite_metadata


def test_yolo_label_parsing_and_pixel_conversion() -> None:
    box = parse_yolo_label_line("0 0.500000 0.250000 0.100000 0.200000")
    assert box is not None
    pixel = yolo_to_pixel_box(box, 1000, 500)

    assert pixel.x1 == pytest.approx(450)
    assert pixel.x2 == pytest.approx(550)
    assert pixel.y1 == pytest.approx(75)
    assert pixel.y2 == pytest.approx(175)


def test_extract_sprites_and_copy_paste_augment(tmp_path: Path) -> None:
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")

    dataset_root = tmp_path / "dataset"
    images_root = dataset_root / "images"
    labels_root = dataset_root / "labels"
    image_dir = images_root / "cam1"
    label_dir = labels_root / "cam1"
    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)

    source_image = np.full((80, 120, 3), 60, dtype=np.uint8)
    cv2.circle(source_image, (60, 40), 10, (35, 210, 220), -1)
    cv2.imwrite(str(image_dir / "ball.jpg"), source_image)
    (label_dir / "ball.txt").write_text("0 0.500000 0.500000 0.200000 0.300000\n", encoding="utf-8")

    background = np.full((80, 120, 3), 95, dtype=np.uint8)
    cv2.imwrite(str(image_dir / "background.jpg"), background)
    (label_dir / "background.txt").write_text("", encoding="utf-8")

    unlabeled_background = np.full((80, 120, 3), 120, dtype=np.uint8)
    cv2.imwrite(str(image_dir / "unlabeled.jpg"), unlabeled_background)

    sprites_root = tmp_path / "sprites"
    result = extract_sprites(
        images_root=images_root,
        labels_root=labels_root,
        excluded_file=dataset_root / "excluded_images.txt",
        output_root=sprites_root,
        feather_px=2,
        overwrite=True,
    )

    assert result.candidates == 1
    metadata_path = next((sprites_root / "candidates").glob("*.json"))
    metadata = load_sprite_metadata(metadata_path)
    assert metadata["status"] == "candidate"
    assert (sprites_root / "candidates" / metadata["files"]["sprite"]).is_file()

    copy_reviewed_sprite(sprites_root, metadata, metadata_path, "approved")
    assert (sprites_root / "approved" / metadata["files"]["sprite"]).is_file()

    config = tmp_path / "augmentation.toml"
    output_root = tmp_path / "augmented"
    config.write_text(
        f"""
[augmentation]
pipeline = "copy_paste"

[inputs]
dataset_root = "{dataset_root.as_posix()}"
sprites_root = "{(sprites_root / "approved").as_posix()}"
excluded_file = "{(dataset_root / "excluded_images.txt").as_posix()}"

[output]
root = "{output_root.as_posix()}"
count = 2
seed = 7
image_format = "jpg"
jpeg_quality = 90

[selection]
allow_labeled_backgrounds = true
prefer_negative_backgrounds = true
require_label_file_backgrounds = true
paste_per_image = [1, 1]

[negative_augmentation]
count = 1

[originals]
include = true

[split]
val_ratio = 0.2
seed = 7

[background]
brightness = [0, 0]
contrast = [1.0, 1.0]
blur_probability = 0.0
blur_kernel = [3, 3]

[frame]
rotate_probability = 1.0
rotate_degrees = [1.5, 1.5]

[ball]
scale = [1.0, 1.0]
stretch_x = [1.0, 1.0]
stretch_y = [1.0, 1.0]
brightness = [0, 0]
contrast = [1.0, 1.0]
rotate_degrees = [-4, 4]
motion_blur_probability = 0.0
motion_blur_kernel = [3, 3]
alpha_threshold_for_bbox = 16
min_visible_area_px = 8
avoid_existing_iou = 0.0
""",
        encoding="utf-8",
    )

    aug_result = copy_paste_augment(config)

    assert aug_result.generated == 3
    assert (output_root / "data.yaml").is_file()
    assert (output_root / "report.md").read_text(encoding="utf-8").startswith("# YOLO Copy-Paste")
    label_files = sorted((output_root / "labels").glob("*.txt"))
    assert len(label_files) == 3
    assert sum(1 for label_path in label_files if not label_path.read_text(encoding="utf-8").strip()) == 1
    for label_path in label_files:
        text = label_path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        payload = text.split()
        assert payload[0] == "0"
        values = [float(value) for value in payload[1:]]
        assert all(0.0 <= value <= 1.0 for value in values)
    manifest_rows = [
        json.loads(line)
        for line in (output_root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(manifest_rows) == 3
    assert {row["kind"] for row in manifest_rows} == {"copy_paste", "negative_augmentation"}
    assert all(row["source_background"] != "cam1/unlabeled.jpg" for row in manifest_rows)
    train_rows = [line for line in (output_root / "train.txt").read_text(encoding="utf-8").splitlines() if line]
    val_rows = [line for line in (output_root / "val.txt").read_text(encoding="utf-8").splitlines() if line]
    assert len(train_rows) + len(val_rows) == 5
    assert any(line.endswith("ball.jpg") for line in train_rows + val_rows)
    assert any(line.endswith("background.jpg") for line in train_rows + val_rows)
    assert all(not line.endswith("unlabeled.jpg") for line in train_rows + val_rows)
    assert (label_dir / "background.txt").read_text(encoding="utf-8") == ""


def test_transform_sprite_supports_anisotropic_stretch() -> None:
    np = pytest.importorskip("numpy")

    sprite = np.zeros((10, 20, 4), dtype=np.uint8)
    resolved = {
        "ball": {
            "scale": (1.0, 1.0),
            "stretch_x": (1.5, 1.5),
            "stretch_y": (0.5, 0.5),
            "brightness": (0, 0),
            "contrast": (1.0, 1.0),
            "rotate_degrees": (0.0, 0.0),
            "motion_blur_probability": 0.0,
            "motion_blur_kernel": (3, 3),
        }
    }

    transformed = transform_sprite(sprite, resolved, rng=__import__("random").Random(1), allow_rotation=False)

    assert transformed.shape[0] == 5
    assert transformed.shape[1] == 30


def test_frame_rotation_transforms_labels_to_axis_aligned_boxes() -> None:
    np = pytest.importorskip("numpy")

    image = np.zeros((100, 120, 3), dtype=np.uint8)
    label = PixelLabel(0, yolo_to_pixel_box(parse_yolo_label_line("0 0.500000 0.500000 0.200000 0.200000"), 120, 100))

    rotated_image, rotated_labels = rotate_frame_and_labels(image, [label], 2.0)

    assert rotated_image.shape == image.shape
    assert len(rotated_labels) == 1
    rotated_box = rotated_labels[0].box
    assert rotated_box.width > label.box.width
    assert rotated_box.height > label.box.height
    assert 0 <= rotated_box.x1 < rotated_box.x2 <= 120
    assert 0 <= rotated_box.y1 < rotated_box.y2 <= 100
