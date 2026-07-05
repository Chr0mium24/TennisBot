# Search-S3l Motion-Diff Temporal Heatmap Result - 2026-07-05

## Scope

This trained a second temporal heatmap search/acquisition model using explicit
adjacent-frame difference maps. It uses labeled image sequences only and does
not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis
control.

Training was manually stopped after epoch `7` because the best held-out recall
remained below S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3l_temporal_heatmap_w5_960x540_rgbdiff_pseudo989_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `5` frames
- Input: `960x540`
- Input mode: `rgb-diff`
- Input channels: `19`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `7`
- Batch: `4`
- Max negative ratio: `1.5`
- Synthetic train samples: `500`

## Best Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `best.pt` | 0.70 | 41 | 14 | 52 | 0.441 | 0.745 | 0.554 | 0.581 | 2.03 |
| `best_recall.pt` | 0.70 | 69 | 153 | 24 | 0.742 | 0.311 | 0.438 | 0.742 | 1.88 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04911 | 0.441 | 0.745 | 0.554 | 0.70 | 0.581 | 0.581 @ 0.50 |
| 2 | 0.01334 | 0.559 | 0.292 | 0.384 | 0.70 | 0.613 | 0.613 @ 0.60 |
| 3 | 0.01013 | 0.667 | 0.257 | 0.371 | 0.70 | 0.677 | 0.677 @ 0.05 |
| 4 | 0.00902 | 0.613 | 0.329 | 0.429 | 0.70 | 0.613 | 0.613 @ 0.70 |
| 5 | 0.00888 | 0.720 | 0.325 | 0.448 | 0.70 | 0.720 | 0.720 @ 0.70 |
| 6 | 0.00817 | 0.742 | 0.311 | 0.438 | 0.70 | 0.742 | 0.742 @ 0.70 |
| 7 | 0.00813 | 0.731 | 0.273 | 0.398 | 0.70 | 0.731 | 0.731 @ 0.70 |

## Latency

Measured after interruption by loading `best_recall.pt` and running the same
random-input model benchmark used by the trainer.

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | rgb-diff 960x540 | 24.08 | 20.76 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Estimated stereo FPS |
|---|---|---:|---:|---:|
| S3d | 5 RGB frames + pseudo989 + synth500 | 0.774 | 0.327 | 21.48 |
| S3l | S3d data, plus explicit frame-difference input maps | 0.742 | 0.311 | 20.76 |

## Decision

S3l did not beat S3d. Adding explicit adjacent-frame difference maps improved
early learning but did not solve the held-out miss pattern, and it slightly
reduced throughput because the input has `19` channels instead of `15`.

The current best search model remains S3d. The next useful step is not another
unreviewed synthetic/self-labeled training run. The remaining recall gap needs
reviewed real positives for held-out-like net/center miss patterns, or a larger
architecture change that specifically reduces wrong-peak localization.
