from __future__ import annotations

from pathlib import Path

from tennisbot_yolo.temporal_heatmap import (
    PeakPrediction,
    build_temporal_samples,
    compute_peak_metrics,
    frame_sort_key,
)


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


def write_label(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


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
