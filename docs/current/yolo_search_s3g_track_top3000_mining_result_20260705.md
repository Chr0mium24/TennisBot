# Temporal Pseudo-Label Mining Result - 2026-07-05

## Settings

- Checkpoint: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt`
- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705`
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
| accepted candidates | 3000 |
| copied base label files | 1222 |
| written pseudo labels | 2930 |
| skipped existing positives | 70 |

## Audit

| item | value |
|---|---:|
| manifest rows | 2930 |
| score min | 0.958693 |
| score median | 0.965087 |
| score p90 | 0.971018 |
| score max | 0.977234 |
| cam1 pseudo labels | 1437 |
| cam2 pseudo labels | 1493 |
| accepted track count in manifest | 288 |
| written track length median | 5 |
| written track length max | 112 |
| output label files | 4127 |
| output nonempty labels | 3520 |
| output empty labels | 607 |

Top pseudo-labeled sequences:

| sequence | pseudo labels |
|---|---:|
| `0260701/20260701_154256_cam1` | 281 |
| `0260701/20260701_154256_cam2` | 220 |
| `0260701/20260701_155529_cam1` | 201 |
| `0260701/20260701_155912_cam1` | 198 |
| `0260701/20260701_155529_cam2` | 187 |
| `0260701/20260701_160045_cam2` | 185 |
| `0260701/20260701_161022_cam2` | 183 |
| `0260701/20260701_160045_cam1` | 135 |
| `0260701/20260701_155912_cam2` | 128 |
| `0260701/20260701_154205_cam1` | 118 |

## Files

- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705/labels`
- Manifest: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705/manifest.csv`
- Candidate audit: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705/candidates.csv`
