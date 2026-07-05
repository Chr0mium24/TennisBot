from __future__ import annotations

from pathlib import Path

from tennisbot_yolo.temporal_heatmap import (
    PeakPrediction,
    TemporalPeakCandidate,
    SyntheticConfig,
    SyntheticTemporalHeatmapDataset,
    HeatmapSample,
    build_mining_temporal_samples,
    build_temporal_samples,
    collect_synthetic_backgrounds,
    collect_synthetic_sprites,
    compute_peak_metrics,
    filter_temporal_tracks,
    frame_sort_key,
)


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def write_label(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_rgb_image(path: Path, width: int = 32, height: int = 24) -> None:
    import cv2
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((height, width, 3), 90, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)


def write_rgba_sprite(path: Path) -> None:
    import cv2
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    sprite = np.zeros((6, 6, 4), dtype=np.uint8)
    sprite[:, :, 1] = 220
    sprite[:, :, 3] = 255
    assert cv2.imwrite(str(path), sprite)


def test_frame_sort_key_uses_numeric_frame_order() -> None:
    paths = [
        Path("seq_frame_000010.jpg"),
        Path("seq_frame_000002.jpg"),
        Path("seq_frame_000001.jpg"),
    ]

    assert [path.name for path in sorted(paths, key=frame_sort_key)] == [
        "seq_frame_000001.jpg",
        "seq_frame_000002.jpg",
        "seq_frame_000010.jpg",
    ]


def test_build_temporal_samples_excludes_validation_token(tmp_path: Path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    for token in ("train_seq", "20260701_155008_cam1"):
        for frame in range(1, 4):
            rel = Path("0260701") / f"{token}_frame_{frame:06d}.jpg"
            touch(images / rel)
            write_label(labels / rel.with_suffix(".txt"), "0 0.500000 0.500000 0.010000 0.010000\n")

    samples = build_temporal_samples(
        images_root=images,
        labels_root=labels,
        window=3,
        exclude_tokens=("20260701_155008",),
    )

    assert len(samples) == 1
    assert samples[0].sequence_key == "0260701/train_seq"
    assert samples[0].frame_index == 2
    assert samples[0].positive is True


def test_build_mining_temporal_samples_does_not_require_labels(tmp_path: Path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    for frame in range(1, 6):
        rel = Path("0260701") / f"train_seq_frame_{frame:06d}.jpg"
        touch(images / rel)

    samples = build_mining_temporal_samples(images_root=images, labels_root=labels, window=3)

    assert [sample.frame_index for sample in samples] == [2, 3, 4]
    assert all(sample.positive is False for sample in samples)


def test_filter_temporal_tracks_requires_consistent_motion() -> None:
    def candidate(frame: int, x: float, score: float = 0.8) -> TemporalPeakCandidate:
        sample = HeatmapSample(
            window_paths=(Path(f"frame_{frame - 1}.jpg"), Path(f"frame_{frame}.jpg"), Path(f"frame_{frame + 1}.jpg")),
            center_image=Path(f"seq_frame_{frame:06d}.jpg"),
            label_path=Path(f"seq_frame_{frame:06d}.txt"),
            sequence_key="seq",
            frame_index=frame,
            positive=False,
        )
        return TemporalPeakCandidate(sample=sample, score=score, x_px=x, y_px=10.0)

    tracks = filter_temporal_tracks(
        [candidate(1, 10.0), candidate(2, 18.0), candidate(3, 26.0), candidate(4, 140.0)],
        min_score=0.7,
        min_track_length=3,
        max_frame_gap=1,
        max_motion_px=12.0,
    )

    assert len(tracks) == 1
    assert [item.sample.frame_index for item in tracks[0].candidates] == [1, 2, 3]


def test_compute_peak_metrics_counts_bad_localization_as_fp_and_fn() -> None:
    predictions = [
        PeakPrediction(score=0.8, x=10.0, y=10.0, positive=True, gt_x=11.0, gt_y=11.0),
        PeakPrediction(score=0.8, x=30.0, y=30.0, positive=True, gt_x=60.0, gt_y=60.0),
        PeakPrediction(score=0.8, x=5.0, y=5.0, positive=False, gt_x=0.0, gt_y=0.0),
    ]

    metrics = compute_peak_metrics(
        predictions,
        width=100,
        height=100,
        radius_px=4.0,
        thresholds=[0.5],
    )

    assert metrics.tp == 1
    assert metrics.fp == 2
    assert metrics.fn == 1
    assert metrics.recall == 0.5
    assert round(metrics.precision, 3) == 0.333


def test_collect_synthetic_backgrounds_skips_positive_and_validation(tmp_path: Path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    train_negative = Path("0260701/train_seq_frame_000001.jpg")
    train_positive = Path("0260701/train_pos_frame_000001.jpg")
    val_negative = Path("0260701/20260701_155008_cam1_frame_000001.jpg")
    for rel in (train_negative, train_positive, val_negative):
        write_rgb_image(images / rel)
    write_label(labels / train_positive.with_suffix(".txt"), "0 0.500000 0.500000 0.100000 0.100000\n")
    write_label(labels / val_negative.with_suffix(".txt"), "")

    backgrounds = collect_synthetic_backgrounds(
        images_root=images,
        labels_root=labels,
        exclude_tokens=("20260701_155008",),
    )

    assert backgrounds == (images / train_negative,)


def test_collect_synthetic_sprites_excludes_validation_token(tmp_path: Path) -> None:
    keep = tmp_path / "train_sprite.png"
    skip = tmp_path / "20260701_155008_cam1_sprite.png"
    write_rgba_sprite(keep)
    write_rgba_sprite(skip)

    sprites = collect_synthetic_sprites(tmp_path, exclude_tokens=("20260701_155008",))

    assert sprites == (keep,)


def test_synthetic_temporal_dataset_returns_positive_heatmap(tmp_path: Path) -> None:
    background = tmp_path / "background.jpg"
    sprite = tmp_path / "sprite.png"
    write_rgb_image(background, width=64, height=48)
    write_rgba_sprite(sprite)
    dataset = SyntheticTemporalHeatmapDataset(
        SyntheticConfig(
            backgrounds=(background,),
            sprites=(sprite,),
            count=1,
            window=3,
            input_width=64,
            input_height=48,
            sigma=2.0,
            seed=123,
            sprite_scale_min=1.0,
            sprite_scale_max=1.0,
            motion_px_min=1.0,
            motion_px_max=2.0,
            motion_angle_deg_min=0.0,
            motion_angle_deg_max=360.0,
            center_x_min=0.0,
            center_x_max=1.0,
            center_y_min=0.0,
            center_y_max=1.0,
            blur_probability=0.0,
            max_sprite_px=16,
        )
    )

    image, target, meta = dataset[0]

    assert tuple(image.shape) == (9, 48, 64)
    assert tuple(target.shape) == (1, 48, 64)
    assert float(target.max()) > 0.9
    assert meta[0].item() == 1.0


def test_synthetic_temporal_dataset_respects_center_range(tmp_path: Path) -> None:
    background = tmp_path / "background.jpg"
    sprite = tmp_path / "sprite.png"
    write_rgb_image(background, width=100, height=80)
    write_rgba_sprite(sprite)
    dataset = SyntheticTemporalHeatmapDataset(
        SyntheticConfig(
            backgrounds=(background,),
            sprites=(sprite,),
            count=3,
            window=3,
            input_width=100,
            input_height=80,
            sigma=2.0,
            seed=456,
            sprite_scale_min=1.0,
            sprite_scale_max=1.0,
            motion_px_min=0.0,
            motion_px_max=0.0,
            motion_angle_deg_min=240.0,
            motion_angle_deg_max=300.0,
            center_x_min=0.45,
            center_x_max=0.55,
            center_y_min=0.50,
            center_y_max=0.65,
            blur_probability=0.0,
            max_sprite_px=16,
        )
    )

    for index in range(len(dataset)):
        _image, _target, meta = dataset[index]
        assert 0.45 <= meta[1].item() <= 0.55
        assert 0.50 <= meta[2].item() <= 0.65
