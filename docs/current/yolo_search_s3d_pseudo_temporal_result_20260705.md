# Search-S3d Pseudo-Label Temporal Heatmap Result - 2026-07-05

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation token: `20260701_155008`
- Train exclude: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Batch: `4`
- Synthetic train samples: `500`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 1785 | 1585 | 200 |
| train_real | 1285 | 1085 | 200 |
| train_synthetic | 500 | 500 | 0 |
| val | 253 | 93 | 160 |

`train_real` includes original labels plus `989` pseudo labels mined from
non-validation continuous windows. Validation remains the real held-out
`20260701_155008` labels.

## Best Validation

### Best F1

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 16 | 0.00806 | 0.70 | 68 | 76 | 25 | 0.731 | 0.472 | 0.574 | 0.731 | 1.53 |

### Best Recall

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 0.00759 | 0.40 | 72 | 148 | 21 | 0.774 | 0.327 | 0.460 | 0.774 | 1.67 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.27 | 21.48 |

## Decision

Search-S3d improves recall, but it still does not reach the requested `>0.90`
recall.

| Model | Added data | Best-F1 recall | Best recall | Best-recall precision | Best F1 |
|---|---|---:|---:|---:|---:|
| S3b | none | 0.559 | 0.613 | 0.350 | 0.698 |
| S3c | 500 synthetic positives | 0.667 | 0.699 | 0.283 | 0.713 |
| S3d | 989 pseudo + 500 synthetic positives | 0.731 | 0.774 | 0.327 | 0.574 |

Interpretation:

- More data is helping recall: saved-checkpoint best recall moved from `0.699`
  to `0.774`.
- The pseudo labels are noisy. Recall increased, but precision and F1 dropped
  compared with S3c.
- This is still an offline teacher. It must not be promoted to CPU runtime.

Next step:

1. Improve pseudo-label quality before scaling quantity: require temporal
   consistency, mine from `best_recall.pt`, or review a candidate batch.
2. Add real continuous cam2 labels. The current non-validation positives are
   still mostly cam1.
3. Train the next teacher against the cleaner expanded label root and keep
   `best_recall.pt` as the recall gate.
