# Search-S3k Pseudo + Hard-Negative + Targeted Synthetic Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using S3j's pseudo + small hard-negative
label root and targeted synthetic positives. It uses labeled image sequences
only and does not validate real ROS/chassis, stereo triangulation, target prediction,
or chassis control.

Training was manually stopped after epoch `5` because recall did not exceed
S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3k_temporal_heatmap_w5_960x540_pseudo_hardneg300_targeted_synth1000_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `5`
- Batch: `4`
- Max negative ratio: `1.5`
- Synthetic train samples: `1000`
- Synthetic type: targeted center/motion distribution
- Hard negatives added: `300`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 2585 | 2085 | 500 |
| train_real | 1585 | 1085 | 500 |
| train_synthetic | 1000 | 1000 | 0 |
| val | 253 | 93 | 160 |

## Best Saved Checkpoint

The saved `best.pt` and `best_recall.pt` point to the same checkpoint.

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | 0.70 | 69 | 120 | 24 | 0.742 | 0.365 | 0.489 | 0.742 | 1.48 |
| best_recall.pt | 0.70 | 69 | 120 | 24 | 0.742 | 0.365 | 0.489 | 0.742 | 1.48 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04600 | 0.194 | 0.720 | 0.305 | 0.70 | 0.409 | 0.409 @ 0.05 |
| 2 | 0.01147 | 0.516 | 0.217 | 0.306 | 0.70 | 0.548 | 0.548 @ 0.05 |
| 3 | 0.00806 | 0.742 | 0.365 | 0.489 | 0.70 | 0.742 | 0.742 @ 0.70 |
| 4 | 0.00853 | 0.710 | 0.261 | 0.382 | 0.05 | 0.710 | 0.710 @ 0.05 |
| 5 | 0.00748 | 0.731 | 0.297 | 0.422 | 0.70 | 0.731 | 0.731 @ 0.70 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.68 | 21.11 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Best F1 |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 0.574 |
| S3j | S3d pseudo base + 300 hard negatives + 500 random synthetic | 0.753 | 0.407 | 0.692 |
| S3k | S3d pseudo base + 300 hard negatives + 1000 targeted synthetic | 0.742 | 0.365 | 0.489 |

## Decision

S3k did not beat S3d. Adding targeted synthetic to the pseudo + small
hard-negative mix did not recover the lost recall.

At this point the generated-data path has repeatedly failed to exceed S3d's
`0.774` recall. The next meaningful step is reviewed real positive labels for
the held-out miss pattern, not more unreviewed synthetic or self-labeled data.
