# Temporal Interpolated Label Generation Result - 2026-07-05

## Settings

- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Base labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap2_20260705`
- Exclude tokens: `20260701_155008`
- Max frame gap: `2`
- Max motion px/frame: `0.0`
- Motion input scale: `960x540`

## Result

| item | count |
|---|---:|
| copied base label files | 2211 |
| selected interpolated labels | 126 |
| written interpolated labels | 126 |
| overwritten empty label files | 3 |
| skipped existing positives | 0 |
| cam1 selected | 72 |
| cam2 selected | 54 |
| other selected | 0 |

## Gap Distribution

| anchor gap | generated labels |
|---:|---:|
| 2 | 126 |

## Top Sequences

| sequence | generated labels |
|---|---:|
| 0260701/20260701_155912_cam1 | 16 |
| 0260701/20260701_155529_cam1 | 14 |
| 0260701/20260701_154256_cam2 | 11 |
| 0260701/20260701_154256_cam1 | 9 |
| 0260701/20260701_161022_cam1 | 9 |
| 0260701/20260701_155529_cam2 | 7 |
| 0260701/20260701_155457_cam2 | 6 |
| 0260701/20260701_160045_cam1 | 6 |
| 0260701/20260701_161022_cam2 | 6 |
| 0260701/20260701_160045_cam2 | 5 |
| 0260701/20260701_154205_cam1 | 4 |
| 0260701/20260701_155038_cam1 | 4 |
| 0260701/20260701_155912_cam2 | 4 |
| 0260701/20260701_154019_cam1 | 3 |
| 0260701/20260701_154812_cam2 | 3 |
| 0260701/20260701_155135_cam1 | 3 |
| 0260701/20260701_155847_cam2 | 3 |
| 0260701/20260701_154019_cam2 | 2 |
| 0260701/20260701_154205_cam2 | 2 |
| 0260701/20260701_155239_cam2 | 2 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap2_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap2_20260705/manifest.csv`
