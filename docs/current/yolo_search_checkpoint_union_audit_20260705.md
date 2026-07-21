# Search Checkpoint Union Audit - 2026-07-05

## Scope

This checks whether existing temporal heatmap checkpoints miss different
held-out frames. It is an offline vision audit only and does not validate
real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Checkpoints

| name | checkpoint | best recall |
|---|---|---:|
| S3d | `tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt` | 0.774 |
| S3e | `tools/yolo/workspace/runs/temporal_heatmap/search_s3e_temporal_heatmap_w7_960x540_pseudo989_synth1000_20260705/best_recall.pt` | 0.753 |
| S3j | `tools/yolo/workspace/runs/temporal_heatmap/search_s3j_temporal_heatmap_w5_960x540_pseudo_hardneg300_synth500_20260705/best_recall.pt` | 0.753 |
| S3k | `tools/yolo/workspace/runs/temporal_heatmap/search_s3k_temporal_heatmap_w5_960x540_pseudo_hardneg300_targeted_synth1000_20260705/best_recall.pt` | 0.742 |
| S3l | `tools/yolo/workspace/runs/temporal_heatmap/search_s3l_temporal_heatmap_w5_960x540_rgbdiff_pseudo989_synth500_20260705/best_recall.pt` | 0.742 |

S3e uses a 7-frame window, so the common validation subset across all
checkpoints is `251` samples instead of S3d's full `253`.

## Result

Sample-level union means a positive is counted as TP if any selected checkpoint
has a peak above threshold within the `12px` match radius. A bad localized peak
without any localized hit is still counted as FP+FN, matching the existing
single-model metric behavior.

| subset | best observed recall | threshold | TP | FP | FN | precision |
|---|---:|---:|---:|---:|---:|---:|
| S3d | 0.774 | 0.05-0.40 | 72 | 146-179 | 21 | 0.287-0.330 |
| S3d+S3j | 0.774 | 0.05-0.40 | 72 | 178-179 | 21 | 0.287-0.288 |
| S3d+S3e | 0.774 | 0.05-0.40 | 72 | 179 | 21 | 0.287 |
| S3d+S3l | 0.774 | 0.05-0.40 | 72 | 179 | 21 | 0.287 |
| S3d+S3e+S3j | 0.774 | 0.05-0.40 | 72 | 179 | 21 | 0.287 |
| S3d+S3e+S3j+S3k+S3l | 0.774 | 0.05-0.40 | 72 | 179 | 21 | 0.287 |

## Decision

Unioning the current checkpoints does not recover any additional held-out
positives. The variants are missing the same frames as S3d, so a simple
multi-model teacher or ensemble pseudo-label source will not create the missing
training signal.

This supports the later S3m/S3n choice to test generated label quality rather
than checkpoint ensembling, and it also reinforces that remaining progress
needs reviewed real positives or a genuinely different localization objective.
