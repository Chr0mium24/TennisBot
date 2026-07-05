# Temporal Hard-Negative Mining Result - 2026-07-05

## Settings

- Candidates CSV: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/candidates.csv`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705`
- Base labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Input: `960x540`
- Score threshold: `0.95`
- X range: `0.1-0.4`
- Y range: `0.25-0.75`
- Max count: `300`

## Result

| item | count |
|---|---:|
| copied base label files | 2211 |
| selected hard negatives | 300 |
| written empty label files | 300 |
| already-empty selected labels | 0 |

## Audit

| item | value |
|---|---:|
| manifest rows | 300 |
| score min | 0.964089 |
| score median | 0.966490 |
| score p90 | 0.970755 |
| score max | 0.975762 |
| cam1 hard negatives | 92 |
| cam2 hard negatives | 208 |
| output label files | 2511 |
| output nonempty labels | 1579 |
| output empty labels | 932 |

Top hard-negative sequences:

| sequence | hard negatives |
|---|---:|
| `0260701/20260701_161022_cam2` | 80 |
| `0260701/20260701_160045_cam2` | 54 |
| `0260701/20260701_155529_cam1` | 23 |
| `0260701/20260701_161022_cam1` | 22 |
| `0260701/20260701_155529_cam2` | 19 |
| `0260701/20260701_155912_cam1` | 18 |
| `0260701/20260701_155912_cam2` | 17 |
| `0260701/20260701_154812_cam2` | 11 |
| `0260701/20260701_160620_cam1` | 7 |
| `0260701/20260701_154812_cam1` | 7 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705/manifest.csv`
