# YOLO Final Raw Benchmark v1 Plan - 2026-07-08

## Purpose

Freeze a raw-image holdout before the next round of YOLO training experiments.
Future full-frame training, ROI crops, copy-paste synthesis, and traditional
augmentation must be derived only from `train_pool.txt`. The files in
`benchmark.txt` are reserved for final reporting across auto-exposure and
fixed-exposure raw datasets.

This split is a detector benchmark setup only. It does not validate camera
capture, stereo triangulation, trajectory prediction, real ROS/chassis, or chassis
control.

## Reproducible Command

```bash
uv run --project tools/yolo python -m tennisbot_yolo.cli benchmark build-final-raw-split
```

Output directory:

`tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708`

Generated files:

- `manifest.jsonl`
- `summary.json`
- `benchmark.txt`
- `benchmark_auto_exposure.txt`
- `benchmark_fixed_exposure.txt`
- `train_pool.txt`
- `train_pool_auto_exposure.txt`
- `train_pool_fixed_exposure.txt`

Manifest SHA256 from the reproducible CLI output:

`80c79c8972bfd8eb5ebca3a1191b9d52e3c5f34453ac1a95860769baa1f370c1`

## Inputs

| dataset | source |
|---|---|
| auto exposure | `tools/yolo/workspace/dataset/images/cam1/device_a_indoor/indoor_ball_sample*_cam1_frame_*.jpg` |
| fixed exposure | `tools/yolo/workspace/runs/fixed_exposure_source_20260707/images/*.jpg` |

The auto-exposure labels are found by replacing `images` with `labels`.
The fixed-exposure labels are under
`tools/yolo/workspace/runs/fixed_exposure_source_20260707/labels`.

## Bucket Policy

Buckets are computed on the raw full-frame label size:

| bucket | rule |
|---|---|
| `small` | `max_box_dim_px < 16` |
| `medium` | `16 <= max_box_dim_px < 48` |
| `large` | `max_box_dim_px >= 48` |
| `empty` | no labels |

## Split Policy

| item | policy |
|---|---|
| auto benchmark holdout | whole session `indoor_ball_sample_cam1` |
| fixed benchmark holdout | whole sessions `20260707_141324_cam1`, `20260707_141634_cam1` |
| cloudy fixed negative holdout | 50 frames sampled from `cloudy_background_cam1` with seed `20260708` |
| train pool | every non-benchmark raw image |

Positive-session leakage is prevented by whole-session holdout. Cloudy is a
pure negative source, so v1 uses a seeded frame-level holdout for that session.

## Counts

Overall:

| split | images |
|---|---:|
| `benchmark` | `381` |
| `train_pool` | `1439` |
| total | `1820` |

By dataset:

| split | dataset | images |
|---|---|---:|
| `benchmark` | auto exposure | `72` |
| `benchmark` | fixed exposure | `309` |
| `train_pool` | auto exposure | `60` |
| `train_pool` | fixed exposure | `1379` |

By target bucket:

| split | dataset | empty | small | medium | large |
|---|---|---:|---:|---:|---:|
| `benchmark` | auto exposure | `6` | `0` | `0` | `66` |
| `benchmark` | fixed exposure | `86` | `112` | `35` | `76` |
| `train_pool` | auto exposure | `17` | `0` | `0` | `43` |
| `train_pool` | fixed exposure | `487` | `312` | `286` | `294` |

Benchmark sessions:

| dataset | session | images |
|---|---|---:|
| auto exposure | `indoor_ball_sample_cam1` | `72` |
| fixed exposure | `20260707_141324_cam1` | `146` |
| fixed exposure | `20260707_141634_cam1` | `113` |
| fixed exposure | `cloudy_background_cam1` | `50` |

Train-pool sessions:

| dataset | session | images |
|---|---|---:|
| auto exposure | `indoor_ball_sample02_cam1` | `60` |
| fixed exposure | `20260707_140826_cam1` | `76` |
| fixed exposure | `20260707_140849_cam1` | `109` |
| fixed exposure | `20260707_140926_cam1` | `121` |
| fixed exposure | `20260707_140949_cam1` | `78` |
| fixed exposure | `20260707_141056_cam1` | `85` |
| fixed exposure | `20260707_141113_cam1` | `81` |
| fixed exposure | `20260707_141130_cam1` | `57` |
| fixed exposure | `20260707_141342_cam1` | `7` |
| fixed exposure | `20260707_141754_cam1` | `332` |
| fixed exposure | `cloudy_background_cam1` | `433` |

## Verification

- `uv run --project tools/yolo python -m tennisbot_yolo.cli benchmark build-final-raw-split`
  regenerated the manifest and summary successfully.
- `uv run --project tools/yolo pytest tools/yolo/tests/test_package_runtime.py`
  passed with `19 passed`.
- `benchmark.txt` and `train_pool.txt` have no path overlap by construction.
- Every manifest row requires a corresponding label file; missing labels fail the
  split builder instead of being silently treated as empty.

## Required Future Evaluation

Each future model candidate should be evaluated on this frozen benchmark with:

- overall recall and precision at low and medium confidence thresholds;
- recall and precision split by `small`, `medium`, and `large`;
- false positives on `empty` frames;
- FPS for the intended runtime mode, including full-frame and ROI/stateful ROI
  variants where relevant;
- separate tables for auto-exposure and fixed-exposure raw images.

The target remains recall above `0.90` with runtime above `50 FPS`, but a model
should not be promoted until the bucketed benchmark and FPS evidence are both
recorded.

## Evaluation Command Template

Full-frame YOLO candidates can be evaluated with:

```bash
uv run --project tools/yolo --extra detect python -m tennisbot_yolo.cli benchmark eval-final-raw \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest.jsonl \
  --model path/to/model.pt \
  --imgsz 960 \
  --conf-values 0.05,0.25 \
  --device 0 \
  --output-markdown docs/current/<result-name>.md
```

The evaluator reports overall, per-dataset, per-bucket, and dataset-plus-bucket
rows. It also records median/p95 ms per image, mono FPS, and estimated stereo
FPS. The timing is an offline detector replay; it is not a camera or real ROS/chassis
closed-loop benchmark.
