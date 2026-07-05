# Search-S3j Pseudo + Small Hard-Negative Temporal Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using the S3c pseudo-positive label root
plus `300` high-score hard negatives. It uses labeled image sequences only and
does not validate ROS/Gazebo, stereo triangulation, target prediction, or
chassis control.

Training was manually stopped after epoch `7` because recall did not exceed
S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3j_temporal_heatmap_w5_960x540_pseudo_hardneg300_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `7`
- Batch: `4`
- Max negative ratio: `1.5`
- Synthetic train samples: `500`
- Hard negatives added: `300`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 2085 | 1585 | 500 |
| train_real | 1585 | 1085 | 500 |
| train_synthetic | 500 | 500 | 0 |
| val | 253 | 93 | 160 |

## Best Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | 0.70 | 54 | 9 | 39 | 0.581 | 0.857 | 0.692 | 0.753 | 2.05 |
| best_recall.pt | 0.60 | 70 | 102 | 23 | 0.753 | 0.407 | 0.528 | 0.753 | 2.04 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.05385 | 0.043 | 0.016 | 0.024 | 0.70 | 0.043 | 0.043 @ 0.70 |
| 2 | 0.01573 | 0.376 | 0.259 | 0.307 | 0.50 | 0.505 | 0.505 @ 0.40 |
| 3 | 0.00904 | 0.591 | 0.253 | 0.355 | 0.60 | 0.602 | 0.602 @ 0.50 |
| 4 | 0.00838 | 0.710 | 0.308 | 0.430 | 0.60 | 0.720 | 0.720 @ 0.50 |
| 5 | 0.00787 | 0.688 | 0.388 | 0.496 | 0.60 | 0.710 | 0.710 @ 0.50 |
| 6 | 0.00745 | 0.581 | 0.857 | 0.692 | 0.70 | 0.753 | 0.753 @ 0.60 |
| 7 | 0.00721 | 0.602 | 0.386 | 0.471 | 0.70 | 0.667 | 0.667 @ 0.60 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 24.07 | 20.77 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Best F1 |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 0.574 |
| S3i | hard negatives + targeted synthetic | 0.677 | 0.253 | 0.762 |
| S3j | S3d pseudo base + 300 hard negatives + 500 synthetic | 0.753 | 0.407 | 0.692 |

## Decision

S3j improves precision compared with S3d, but it still does not beat S3d recall
and does not approach the requested `>0.90`.

Small hard negatives are less damaging than S3i's full hard-negative set, but
they still do not add the missing positive signal needed for the held-out
trajectory/background pattern.
