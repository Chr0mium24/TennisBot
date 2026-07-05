# Temporal Hard-Negative Mining Result - 2026-07-05

## Settings

- Candidates CSV: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/candidates.csv`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705`
- Base labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/labels`
- Input: `960x540`
- Score threshold: `0.95`
- X range: `0.1-0.4`
- Y range: `0.25-0.75`
- Max count: `0`

## Result

| item | count |
|---|---:|
| copied base label files | 1222 |
| selected hard negatives | 1153 |
| written empty label files | 1153 |
| already-empty selected labels | 0 |

## Audit

| item | value |
|---|---:|
| manifest rows | 1153 |
| score min | 0.950015 |
| score median | 0.961310 |
| score p90 | 0.967790 |
| score max | 0.975762 |
| cam1 hard negatives | 435 |
| cam2 hard negatives | 718 |
| output label files | 2375 |
| output nonempty labels | 590 |
| output empty labels | 1785 |

Top hard-negative sequences:

| sequence | hard negatives |
|---|---:|
| `0260701/20260701_160045_cam2` | 217 |
| `0260701/20260701_161022_cam2` | 193 |
| `0260701/20260701_161022_cam1` | 128 |
| `0260701/20260701_155529_cam1` | 97 |
| `0260701/20260701_155912_cam2` | 77 |
| `0260701/20260701_155912_cam1` | 73 |
| `0260701/20260701_155529_cam2` | 69 |
| `0260701/20260701_160620_cam1` | 69 |
| `0260701/20260701_160620_cam2` | 52 |
| `0260701/20260701_155847_cam2` | 36 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705/manifest.csv`
