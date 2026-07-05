# Search-S3n Gap2 Interpolated Pseudo Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using the stricter gap2 interpolation
label root. It uses labeled image sequences only and does not validate
ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

Training was manually stopped after epoch `5` because recall stayed below S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3n_temporal_heatmap_w5_960x540_interp_gap2_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap2_20260705/labels`
- Interpolated labels added: `126`
- Window: `5` frames
- Input: `960x540`
- Input mode: `rgb`
- Sigma: `4.0` px
- Validation radius: `12` px
- Validation token: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Epochs run: `5`
- Batch: `4`
- Max negative ratio: `1.5`
- Synthetic train samples: `500`

## Best Saved Checkpoints

| checkpoint | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `best.pt` | 0.70 | 61 | 143 | 32 | 0.656 | 0.299 | 0.411 | 0.677 | 1.36 |
| `best_recall.pt` | 0.05 | 65 | 188 | 28 | 0.699 | 0.257 | 0.376 | 0.699 | 1.77 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04742 | 0.258 | 0.960 | 0.407 | 0.70 | 0.473 | 0.473 @ 0.05 |
| 2 | 0.01258 | 0.559 | 0.206 | 0.301 | 0.05 | 0.559 | 0.559 @ 0.05 |
| 3 | 0.01026 | 0.591 | 0.294 | 0.393 | 0.70 | 0.624 | 0.624 @ 0.60 |
| 4 | 0.00981 | 0.656 | 0.299 | 0.411 | 0.70 | 0.677 | 0.677 @ 0.60 |
| 5 | 0.00955 | 0.688 | 0.259 | 0.376 | 0.70 | 0.699 | 0.699 @ 0.05 |

## Latency

Measured after interruption by loading `best_recall.pt` and running the same
random-input model benchmark used by the trainer.

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | rgb 960x540 | 24.06 | 20.78 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Estimated stereo FPS |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 21.48 |
| S3m | gap5 interpolation, 751 labels | 0.710 | 0.262 | 20.77 |
| S3n | gap2 interpolation, 126 labels | 0.699 | 0.257 | 20.78 |

## Decision

S3n did not beat S3d or S3m. Tightening interpolation from gap5 to gap2
reduced generated-label quantity but did not improve held-out recall.

The interpolation path is not the next useful generated-data direction. The
remaining gap is consistent with the earlier miss audit and checkpoint-union
check: the current teacher family does not produce the missing net/center ball
signal. Reaching recall above `0.90` likely requires reviewed real positives for
that miss pattern, or a different training target that teaches the model to
prefer the ball over the ceiling/left-side distractor peaks.
