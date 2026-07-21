# Search-S3 Temporal Heatmap Result - 2026-07-06

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_small_heatmap_w3_480x270_pseudo989_synth500_20260706`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `3` frames
- Input: `480x270`
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
| train | 1789 | 1587 | 202 |
| train_real | 1289 | 1087 | 202 |
| train_synthetic | 500 | 500 | 0 |
| train_weighted_by_manifest | 0 | 0 | 0 |
| val | 255 | 93 | 162 |

## Best Validation

### Best F1

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 0.00894 | 0.70 | 53 | 50 | 40 | 0.570 | 0.515 | 0.541 | 0.688 | 0.80 |

### Best Recall

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.00781 | 0.70 | 66 | 182 | 27 | 0.710 | 0.266 | 0.387 | 0.710 | 0.81 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| auto | rgb 480x270 | 3.95 | 126.57 |

## Decision

This is a teacher experiment. It should not be promoted to the CPU runtime unless recall is high and latency is separately validated in the full ROI/search loop.
