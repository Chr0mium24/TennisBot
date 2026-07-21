# Search-S3i Hard-Negative Temporal Heatmap Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using S3d-derived hard negatives plus
targeted synthetic positives. It uses labeled image sequences only and does not
validate real ROS/chassis, stereo triangulation, target prediction, or chassis
control.

Training was manually stopped after epoch `4` because recall stayed below S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3i_temporal_heatmap_w5_960x540_hardneg_targeted_synth2500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `4`
- Batch: `4`
- Max negative ratio: `12`
- Synthetic train samples: `2500`
- Hard negatives mined: `1153`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 3748 | 2596 | 1152 |
| train_real | 1248 | 96 | 1152 |
| train_synthetic | 2500 | 2500 | 0 |
| val | 253 | 93 | 160 |

## Best Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | 0.70 | 61 | 6 | 32 | 0.656 | 0.910 | 0.762 | 0.677 | 1.38 |
| best_recall.pt | 0.05 | 63 | 186 | 30 | 0.677 | 0.253 | 0.368 | 0.677 | 1.41 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.03149 | 0.247 | 0.885 | 0.387 | 0.60 | 0.333 | 0.333 @ 0.05 |
| 2 | 0.00831 | 0.398 | 0.841 | 0.540 | 0.50 | 0.473 | 0.473 @ 0.20 |
| 3 | 0.00686 | 0.527 | 0.860 | 0.653 | 0.60 | 0.645 | 0.634 @ 0.05 |
| 4 | 0.00669 | 0.656 | 0.910 | 0.762 | 0.70 | 0.677 | 0.677 @ 0.05 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.46 | 21.31 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Best F1 |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 0.574 |
| S3h | targeted synthetic 2500 positives, no hard negatives | 0.720 | 0.753 | 0.736 |
| S3i | hard negatives + targeted synthetic | 0.677 | 0.253 | 0.762 |

## Decision

S3i suppresses false positives strongly, but recall drops further. This confirms
that the hard-negative idea is useful for precision, but this run uses too many
negative samples or too little real positive coverage for the held-out failure
pattern.

Do not continue this exact configuration. A smaller hard-negative subset may be
worth testing, but the main gap remains real positive signal for the held-out
trajectory/background pattern.
