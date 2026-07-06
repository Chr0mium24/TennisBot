# Search-S3 Temporal Heatmap Result - 2026-07-06

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_small_heatmap_w5_640x360_pseudo989_synth500_20260706`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `5` frames
- Input: `640x360`
- Input mode: `rgb`
- Sigma: `2.0` px
- Validation token: `20260701_155008`
- Train exclude: `20260701_155008`
- Device: `auto`
- Epochs requested: `30`
- Batch: `8`
- Synthetic train samples: `500`
- Sample weight manifests: ``
- Manifest sample weight: `1.0`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 1785 | 1585 | 200 |
| train_real | 1285 | 1085 | 200 |
| train_synthetic | 500 | 500 | 0 |
| train_weighted_by_manifest | 0 | 0 | 0 |
| val | 253 | 93 | 160 |

## Best Validation

### Best F1

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 0.00517 | 0.60 | 66 | 116 | 27 | 0.710 | 0.363 | 0.480 | 0.731 | 1.18 |

### Best Recall

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 0.00505 | 0.60 | 69 | 180 | 24 | 0.742 | 0.277 | 0.404 | 0.742 | 1.17 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| auto | rgb 640x360 | 8.91 | 56.14 |

## Decision

This is a teacher experiment. It should not be promoted to the CPU runtime unless recall is high and latency is separately validated in the full ROI/search loop.
