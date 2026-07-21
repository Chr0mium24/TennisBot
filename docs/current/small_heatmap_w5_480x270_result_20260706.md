# Search-S3 Temporal Heatmap Result - 2026-07-06

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_small_heatmap_w5_480x270_pseudo989_synth500_20260706`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `5` frames
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
| train | 1785 | 1585 | 200 |
| train_real | 1285 | 1085 | 200 |
| train_synthetic | 500 | 500 | 0 |
| train_weighted_by_manifest | 0 | 0 | 0 |
| val | 253 | 93 | 160 |

## Best Validation

### Best F1

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 19 | 0.00816 | 0.70 | 66 | 154 | 27 | 0.710 | 0.300 | 0.422 | 0.710 | 0.90 |

### Best Recall

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 17 | 0.00816 | 0.70 | 67 | 162 | 26 | 0.720 | 0.293 | 0.416 | 0.720 | 0.86 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| auto | rgb 480x270 | 4.74 | 105.43 |

## Decision

This is a teacher experiment. It should not be promoted to the CPU runtime unless recall is high and latency is separately validated in the full ROI/search loop.
