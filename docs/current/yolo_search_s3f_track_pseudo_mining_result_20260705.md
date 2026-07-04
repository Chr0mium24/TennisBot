# Temporal Pseudo-Label Mining Result - 2026-07-05

## Settings

- Checkpoint: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Base labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/labels`
- Window: `5`
- Input: `960x540`
- Device: `cuda:0`
- Include tokens: ``
- Exclude tokens: `20260701_155008`
- Score threshold: `0.7`
- Min track length: `3`
- Max frame gap: `1`
- Max motion px/frame: `48.0`
- Box size: `0.005952x0.010871`

## Result

| item | count |
|---|---:|
| scanned windows | 16790 |
| candidates above threshold | 11799 |
| accepted tracks | 890 |
| accepted candidates | 7592 |
| copied base label files | 1222 |
| written pseudo labels | 7503 |
| skipped existing positives | 89 |

## Audit

| item | value |
|---|---:|
| manifest rows | 7503 |
| score min | 0.700247 |
| score median | 0.951779 |
| score p90 | 0.968029 |
| score max | 0.977234 |
| cam1 pseudo labels | 3974 |
| cam2 pseudo labels | 3529 |
| accepted track count in manifest | 888 |
| written track length median | 4 |
| written track length max | 189 |
| output label files | 8693 |
| output nonempty labels | 8093 |
| output empty labels | 600 |

Top pseudo-labeled sequences:

| sequence | pseudo labels |
|---|---:|
| `0260701/20260701_155529_cam1` | 750 |
| `0260701/20260701_155529_cam2` | 567 |
| `0260701/20260701_161022_cam1` | 521 |
| `0260701/20260701_155912_cam1` | 494 |
| `0260701/20260701_155912_cam2` | 442 |
| `0260701/20260701_155457_cam1` | 431 |
| `0260701/20260701_161022_cam2` | 408 |
| `0260701/20260701_154256_cam1` | 369 |
| `0260701/20260701_155847_cam2` | 345 |
| `0260701/20260701_154256_cam2` | 300 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/manifest.csv`
- Candidate audit: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/candidates.csv`
