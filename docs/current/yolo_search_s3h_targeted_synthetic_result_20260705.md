# Search-S3h Targeted Synthetic Temporal Heatmap Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher with targeted synthetic positives aimed
at the S3d held-out miss pattern. It uses labeled image sequences only and does
not validate real ROS/chassis, stereo triangulation, target prediction, or chassis
control.

Training was manually stopped after epoch `6` because recall did not exceed
S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3h_temporal_heatmap_w5_960x540_targeted_synth2500_20260705`
- Labels root: `tools/yolo/workspace/dataset/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `6`
- Batch: `4`
- Synthetic train samples: `2500`
- Synthetic center x: `0.42-0.58`
- Synthetic center y: `0.45-0.68`
- Synthetic motion: `4-28` px/frame
- Synthetic motion angle: `210-330` degrees
- Synthetic blur probability: `0.35`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 2740 | 2596 | 144 |
| train_real | 240 | 96 | 144 |
| train_synthetic | 2500 | 2500 | 0 |
| val | 253 | 93 | 160 |

## Best Saved Checkpoint

The saved `best.pt` and `best_recall.pt` point to the same checkpoint.

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | 0.70 | 67 | 22 | 26 | 0.720 | 0.753 | 0.736 | 0.720 | 1.46 |
| best_recall.pt | 0.70 | 67 | 22 | 26 | 0.720 | 0.753 | 0.736 | 0.720 | 1.46 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04269 | 0.376 | 0.224 | 0.281 | 0.10 | 0.376 | 0.376 @ 0.10 |
| 2 | 0.01199 | 0.495 | 0.868 | 0.630 | 0.70 | 0.602 | 0.602 @ 0.60 |
| 3 | 0.00930 | 0.720 | 0.753 | 0.736 | 0.70 | 0.720 | 0.720 @ 0.70 |
| 4 | 0.00880 | 0.591 | 0.462 | 0.519 | 0.70 | 0.591 | 0.591 @ 0.70 |
| 5 | 0.00852 | 0.624 | 0.725 | 0.671 | 0.70 | 0.699 | 0.699 @ 0.20 |
| 6 | 0.00851 | 0.645 | 0.237 | 0.347 | 0.05 | 0.645 | 0.645 @ 0.05 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 24.06 | 20.78 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Best F1 |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 0.574 |
| S3g | top-score 2930 track pseudo + 500 synthetic positives | 0.742 | 0.294 | 0.593 |
| S3h | targeted synthetic 2500 positives, no pseudo | 0.720 | 0.753 | 0.736 |

## Decision

S3h improves precision and F1, but it does not improve recall and does not
reach the requested `>0.90` recall.

Targeted synthetic data alone is not enough. The remaining recall gap now needs
real labels or reviewed hard examples from sequences with the same ceiling/net
distractor pattern.
