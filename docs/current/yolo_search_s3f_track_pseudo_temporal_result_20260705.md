# Search-S3f Track-Pseudo Temporal Heatmap Result - 2026-07-05

## Scope

This trains the temporal heatmap teacher with the full track-filtered pseudo
label root from S3f mining. It uses labeled image sequences only and does not
validate ROS/Gazebo, stereo triangulation, target prediction, or chassis
control.

## Settings

- Labels root:
  `tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Synthetic train samples: `500`

## Training Status

Training was manually stopped after epoch `1`.

| epoch | loss | threshold | recall | precision | F1 | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.02375 | 0.05 | 0.667 | 0.245 | 0.358 | 0.667 | 0.667 @ 0.05 |

## Decision

The full `7503` written pseudo-label set is too heavy and likely still too
noisy for a first training pass:

- epoch 1 recall is below S3d's `0.774`;
- precision is poor at `0.245`;
- one epoch is substantially slower than prior S3 runs.

Do not continue this full-label S3f configuration. The next step is to train a
smaller high-score track subset so the model sees more data than S3d but not
the full noisy pseudo-label set.
