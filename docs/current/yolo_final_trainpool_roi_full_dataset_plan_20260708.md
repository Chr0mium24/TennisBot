# YOLO Final Train-Pool ROI/Full Dataset Plan - 2026-07-08

## Purpose

Build the next training dataset only from the v1 final benchmark `train_pool`.
The previous packaged baseline is fast enough but misses fixed-exposure
small/medium balls, so this dataset emphasizes fixed-exposure ROI crops while
keeping a 1080p full-frame path for scale diversity.

This is a detector dataset plan only. It does not validate camera capture,
stereo triangulation, trajectory prediction, ROS/Gazebo, or chassis control.

## Command

```bash
uv run --project tools/yolo --extra augment python -m tennisbot_yolo.cli augment build-final-trainset \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest.jsonl \
  --output-root tools/yolo/workspace/runs/final_trainpool_roi_full_20260708 \
  --roi-positive-count 5000 \
  --negative-crop-count 1500 \
  --seed 20260708
```

## Leakage Policy

- Only rows with `split == train_pool` from the final raw benchmark manifest are
  read.
- Frozen `benchmark` rows are not used for full-frame samples, ROI crops,
  negatives, or augmentation.
- Train/val assignment is grouped by source image, so generated samples from one
  raw frame cannot appear in both train and val.
- ROI windows are clamped inside the source image. No black padding, reflection
  padding, blur fill, or synthetic border fill is used.

## Planned Counts

Dry-run command:

```bash
uv run --project tools/yolo python -m tennisbot_yolo.cli augment build-final-trainset \
  --dry-run \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest.jsonl \
  --roi-positive-count 5000 \
  --negative-crop-count 1500
```

Dry-run result:

| item | count |
|---|---:|
| train-pool source images | `1439` |
| source images assigned train | `1295` |
| source images assigned val | `144` |
| planned 1920x1080 full-frame images | `1439` |
| planned positive ROI crops | `5000` |
| planned empty ROI crops | `1500` |
| planned total images before skipped crops | `7939` |

Source buckets:

| bucket | count |
|---|---:|
| `small` | `312` |
| `medium` | `286` |
| `large` | `337` |
| `empty` | `504` |

Source datasets:

| dataset | count |
|---|---:|
| auto exposure | `60` |
| fixed exposure | `1379` |

## Generation Policy

Image kinds:

| kind | output shape | label policy |
|---|---:|---|
| `full1080` | `1920x1080` | resize raw full frame and preserve labels |
| `roi_positive` | `1024x576` | crop around a labeled ball with varied anchor positions |
| `roi_negative` | `1024x576` | random crop from empty train-pool frames |

Positive ROI source weighting:

| source bucket | weight |
|---|---:|
| `small` | `7.0` |
| `medium` | `4.0` |
| `large` | `1.0` |

Fixed-exposure positives are multiplied by `1.25`; auto-exposure positives are
multiplied by `0.75`. This intentionally focuses generation on the failure mode
seen in the final benchmark.

ROI ball anchor grid:

```text
0.18, 0.32, 0.50, 0.68, 0.82
```

Traditional augmentation ranges:

| parameter | value |
|---|---:|
| brightness beta | `[-70, 70]` |
| contrast alpha | `[0.65, 1.45]` |
| saturation scale | `[0.60, 1.55]` |
| value scale | `[0.70, 1.40]` |
| horizontal flip probability | `0.25` |
| rotation probability | `0.35` |
| rotation degrees | `[-2.0, 2.0]` |
| Gaussian blur probability | `0.12` |
| Gaussian blur kernel | `3` or `5` |
| Gaussian noise probability | `0.20` |
| Gaussian noise sigma | `[2.0, 8.0]` |

## Smoke Verification

A local smoke run generated `1445` images with:

```bash
uv run --project tools/yolo --extra augment python -m tennisbot_yolo.cli augment build-final-trainset \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest.jsonl \
  --output-root tools/yolo/workspace/runs/final_trainpool_smoke_20260708 \
  --roi-positive-count 4 \
  --negative-crop-count 2 \
  --seed 20260708
```

Checks:

- generated images: `1445`
- `full1080`: `1439`
- `roi_positive`: `4`
- `roi_negative`: `2`
- source split violations: `0`
- invalid YOLO labels: `0`

## Next Step

Generate the full dataset on the training machine, train from
`artifacts/models/tennis_ball_yolo/model.pt`, then evaluate with the frozen
final benchmark using `benchmark eval-final-raw`.
