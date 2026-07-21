# Search-S3g Track Top3000 Temporal Heatmap Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using the top-score track-filtered pseudo
label root. It uses labeled image sequences only and does not validate
real ROS/chassis, stereo triangulation, target prediction, or chassis control.

Training was manually stopped after epoch `6` because validation recall did not
exceed S3d and the curve was not moving toward `>0.90`.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3g_temporal_heatmap_w5_960x540_tracktop3000_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `6`
- Batch: `4`
- Synthetic train samples: `500`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 3701 | 3526 | 175 |
| train_real | 3201 | 3026 | 175 |
| train_synthetic | 500 | 500 | 0 |
| val | 253 | 93 | 160 |

## Best Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | 0.60 | 43 | 9 | 50 | 0.462 | 0.827 | 0.593 | 0.570 | 1.58 |
| best_recall.pt | 0.40 | 69 | 166 | 24 | 0.742 | 0.294 | 0.421 | 0.742 | 1.64 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04192 | 0.462 | 0.827 | 0.593 | 0.60 | 0.570 | 0.570 @ 0.30 |
| 2 | 0.00967 | 0.613 | 0.333 | 0.432 | 0.70 | 0.720 | 0.720 @ 0.05 |
| 3 | 0.00867 | 0.645 | 0.345 | 0.449 | 0.70 | 0.688 | 0.688 @ 0.50 |
| 4 | 0.00892 | 0.710 | 0.353 | 0.471 | 0.70 | 0.742 | 0.742 @ 0.40 |
| 5 | 0.00819 | 0.645 | 0.349 | 0.453 | 0.70 | 0.720 | 0.720 @ 0.40 |
| 6 | 0.00817 | 0.720 | 0.390 | 0.506 | 0.70 | 0.720 | 0.720 @ 0.70 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.87 | 20.95 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Estimated stereo FPS |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 21.48 |
| S3f | full 7503 track pseudo + 500 synthetic positives | 0.667 after epoch 1 | 0.245 | not measured |
| S3g | top-score 2930 track pseudo + 500 synthetic positives | 0.742 | 0.294 | 20.95 |

## Decision

S3g did not reach the requested `>0.90` recall and did not beat S3d.
Top-score temporal pseudo labels are cleaner than the full S3f set, but
self-training is still not closing the recall gap on held-out real labels.

Next work should shift from adding more self-labeled pseudo data to auditing the
misses and adding/reviewing real continuous labels, especially for the held-out
failure patterns.
