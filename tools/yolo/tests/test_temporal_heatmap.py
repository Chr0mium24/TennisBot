from __future__ import annotations

from pathlib import Path

from tennisbot_yolo.temporal_heatmap import (
    PeakPrediction,
    TemporalPeakCandidate,
    SyntheticConfig,
    SyntheticTemporalHeatmapDataset,
    HeatmapSample,
    TemporalHeatmapDataset,
    build_mining_temporal_samples,
    build_temporal_samples,
    collect_synthetic_backgrounds,
    collect_synthetic_sprites,
    compose_temporal_input,
    compute_peak_metrics,
    filter_temporal_tracks,
    frame_sort_key,
    input_channels_for_mode,
    load_sample_weight_manifests,
    select_interpolated_label_candidates,
    select_hard_negative_candidates,
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


def test_temporal_dataset_uses_manifest_sample_weight(tmp_path: Path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    rel = Path("seq") / "train_cam1_frame_000002.jpg"
    for frame in range(1, 4):
        frame_rel = Path("seq") / f"train_cam1_frame_{frame:06d}.jpg"
        write_rgb_image(images / frame_rel)
    write_label(labels / rel.with_suffix(".txt"), "0 0.500000 0.500000 0.100000 0.100000\n")
    manifest = tmp_path / "manifest.csv"
    manifest.write_text(
        "image,label\n"
        f"{rel.as_posix()},{rel.with_suffix('.txt').as_posix()}\n",
        encoding="utf-8",
    )
    samples = build_temporal_samples(images_root=images, labels_root=labels, window=3, include_empty_labels=True)
    weights = load_sample_weight_manifests((manifest,), labels_root=labels, sample_weight=0.25)

    dataset = TemporalHeatmapDataset(
        samples=samples,
        input_width=32,
        input_height=24,
        sigma=2.0,
        augment=False,
        sample_weights=weights,
    )

    _image, _target, meta = dataset[0]

    assert meta[0].item() == 1.0
    assert meta[3].item() == 0.25


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


def test_select_hard_negative_candidates_skips_positive_labels(tmp_path: Path) -> None:
    candidates = tmp_path / "candidates.csv"
    labels = tmp_path / "labels"
    write_label(labels / "seq/positive_frame_000001.txt", "0 0.500000 0.500000 0.100000 0.100000\n")
    write_label(labels / "seq/empty_frame_000002.txt", "")
    candidates.write_text(
        "\n".join(
            [
                "image,sequence,frame,score,x_px,y_px,status,track_id,track_length",
                "seq/positive_frame_000001.jpg,seq/positive,1,0.990000,200,200,track_rejected,,",
                "seq/empty_frame_000002.jpg,seq/empty,2,0.980000,220,220,track_rejected,,",
                "seq/missing_frame_000003.jpg,seq/missing,3,0.970000,230,230,track_rejected,,",
                "seq/low_frame_000004.jpg,seq/low,4,0.700000,230,230,track_rejected,,",
                "seq/out_frame_000005.jpg,seq/out,5,0.990000,900,20,track_rejected,,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    selected = select_hard_negative_candidates(
        candidates_csv=candidates,
        base_labels_root=labels,
        threshold=0.95,
        input_width=1000,
        input_height=1000,
        x_min=0.1,
        x_max=0.4,
        y_min=0.1,
        y_max=0.4,
        max_count=0,
    )

    assert [candidate.image for candidate in selected] == [
        "seq/empty_frame_000002.jpg",
        "seq/missing_frame_000003.jpg",
    ]
    assert selected[0].preexisting_empty is True
    assert selected[1].preexisting_empty is False


def test_select_interpolated_label_candidates_between_positive_anchors(tmp_path: Path) -> None:
    images = tmp_path / "images"
    labels = tmp_path / "labels"
    for frame in range(1, 6):
        rel = Path("seq") / f"train_cam1_frame_{frame:06d}.jpg"
        write_rgb_image(images / rel)
    write_label(labels / "seq/train_cam1_frame_000001.txt", "0 0.100000 0.200000 0.020000 0.030000\n")
    write_label(labels / "seq/train_cam1_frame_000003.txt", "0 0.300000 0.400000 0.040000 0.050000\n")
    write_label(labels / "seq/train_cam1_frame_000005.txt", "0 0.900000 0.900000 0.060000 0.070000\n")
    write_label(labels / "seq/train_cam1_frame_000004.txt", "")

    selected = select_interpolated_label_candidates(
        images_root=images,
        base_labels_root=labels,
        exclude_tokens=(),
        max_frame_gap=3,
        max_motion_px=0.0,
        input_width=100,
        input_height=100,
    )

    assert [(item.frame, round(item.x_center, 3), round(item.y_center, 3)) for item in selected] == [
        (2, 0.2, 0.3),
        (4, 0.6, 0.65),
    ]
    assert selected[0].preexisting_empty is False
    assert selected[1].preexisting_empty is True


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


def test_rgb_diff_input_appends_frame_difference_maps() -> None:
    import torch

    frames = [
        torch.zeros((3, 4, 5), dtype=torch.float32),
        torch.full((3, 4, 5), 0.25, dtype=torch.float32),
        torch.full((3, 4, 5), 1.00, dtype=torch.float32),
    ]

    tensor = compose_temporal_input(frames, "rgb-diff")

    assert input_channels_for_mode(3, "rgb-diff") == 11
    assert tuple(tensor.shape) == (11, 4, 5)
    assert torch.allclose(tensor[9], torch.full((4, 5), 0.25))
    assert torch.allclose(tensor[10], torch.full((4, 5), 0.75))


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
