# Search-S3o Weighted Interpolation Partial Result - 2026-07-05

## Scope

This is a partial result for S3o. The run was interrupted while summarizing the
project, so the trainer did not write its normal final report. The saved
checkpoints were loaded post-interruption to record the available metrics.

This is an offline vision experiment only and does not validate ROS/Gazebo,
stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3o_temporal_heatmap_w5_960x540_interp_gap5_w025_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels`
- Sample weight manifest: `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/manifest.csv`
- Manifest sample weight: `0.25`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Synthetic train samples: `500`

## Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `best.pt` | 0.70 | 34 | 50 | 59 | 0.366 | 0.405 | 0.384 | 0.548 | 0.97 |
| `best_recall.pt` | 0.70 | 62 | 190 | 31 | 0.667 | 0.246 | 0.359 | 0.667 | 1.21 |

## Observed Early Trace

The visible stdout before interruption included:

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.03208 | 0.366 | 0.405 | 0.384 | 0.70 | 0.548 | 0.548 @ 0.05 |
| 2 | 0.00922 | 0.634 | 0.235 | 0.343 | 0.70 | 0.634 | 0.634 @ 0.70 |
| 3 | 0.00799 | 0.462 | 0.247 | 0.322 | 0.70 | 0.538 | 0.538 @ 0.05 |

The checkpoint timestamp shows a later best-recall checkpoint was written before
the process was stopped, reaching `0.667`.

## Decision

S3o did not approach S3d's `0.774` recall. Downweighting generated interpolation
labels was less destructive than full-weight gap5 early in training, but it did
not create a useful path toward `>0.90` recall.
