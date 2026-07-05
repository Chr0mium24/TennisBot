# Temporal Interpolated Label Generation Result - 2026-07-05

## Settings

- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Base labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705`
- Exclude tokens: `20260701_155008`
- Max frame gap: `5`
- Max motion px/frame: `0.0`
- Motion input scale: `960x540`

## Result

| item | count |
|---|---:|
| copied base label files | 2211 |
| selected interpolated labels | 751 |
| written interpolated labels | 751 |
| overwritten empty label files | 3 |
| skipped existing positives | 0 |
| cam1 selected | 395 |
| cam2 selected | 356 |
| other selected | 0 |

## Gap Distribution

| anchor gap | generated labels |
|---:|---:|
| 2 | 126 |
| 3 | 194 |
| 4 | 207 |
| 5 | 224 |

## Top Sequences

| sequence | generated labels |
|---|---:|
| 0260701/20260701_155912_cam1 | 83 |
| 0260701/20260701_155529_cam2 | 64 |
| 0260701/20260701_155529_cam1 | 61 |
| 0260701/20260701_160045_cam1 | 57 |
| 0260701/20260701_154256_cam1 | 49 |
| 0260701/20260701_155912_cam2 | 49 |
| 0260701/20260701_160045_cam2 | 49 |
| 0260701/20260701_154256_cam2 | 47 |
| 0260701/20260701_161022_cam1 | 45 |
| 0260701/20260701_161022_cam2 | 32 |
| 0260701/20260701_155457_cam2 | 27 |
| 0260701/20260701_154019_cam2 | 24 |
| 0260701/20260701_154205_cam1 | 22 |
| 0260701/20260701_155038_cam2 | 20 |
| 0260701/20260701_154812_cam1 | 19 |
| 0260701/20260701_155457_cam1 | 17 |
| 0260701/20260701_155038_cam1 | 16 |
| 0260701/20260701_155847_cam2 | 16 |
| 0260701/20260701_160620_cam1 | 12 |
| 0260701/20260701_155239_cam2 | 10 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/manifest.csv`
