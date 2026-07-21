# Search-S3m Interpolated Pseudo Temporal Result - 2026-07-05

## Scope

This trains a temporal heatmap teacher using generated interpolation labels
between adjacent positive anchors in the S3c pseudo label root. It uses labeled
image sequences only and does not validate real ROS/chassis, stereo triangulation,
target prediction, or chassis control.

Training was manually stopped after epoch `5` because recall stayed below S3d.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3m_temporal_heatmap_w5_960x540_interp_gap5_synth500_20260705`
- Labels root: `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels`
- Interpolated labels added: `751`
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
| `best.pt` | 0.70 | 64 | 164 | 29 | 0.688 | 0.281 | 0.399 | 0.699 | 1.20 |
| `best_recall.pt` | 0.60 | 66 | 186 | 27 | 0.710 | 0.262 | 0.383 | 0.710 | 1.26 |

## Epoch Trace

| epoch | loss | recall | precision | F1 | threshold | oracle recall | best-recall selection |
|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | 0.04768 | 0.161 | 0.080 | 0.107 | 0.50 | 0.161 | 0.161 @ 0.50 |
| 2 | 0.01666 | 0.333 | 0.126 | 0.182 | 0.70 | 0.333 | 0.333 @ 0.70 |
| 3 | 0.01241 | 0.602 | 0.271 | 0.373 | 0.70 | 0.634 | 0.634 @ 0.60 |
| 4 | 0.01180 | 0.688 | 0.281 | 0.399 | 0.70 | 0.699 | 0.699 @ 0.60 |
| 5 | 0.01157 | 0.710 | 0.262 | 0.383 | 0.60 | 0.710 | 0.710 @ 0.60 |

## Latency

Measured after interruption by loading `best_recall.pt` and running the same
random-input model benchmark used by the trainer.

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | rgb 960x540 | 24.07 | 20.77 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Estimated stereo FPS |
|---|---|---:|---:|---:|
| S3d | 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 21.48 |
| S3m | S3c pseudo root + 751 gap-interpolated positives + 500 synthetic | 0.710 | 0.262 | 20.77 |

## Decision

S3m did not beat S3d. The generated interpolation labels increased data volume
and eventually recovered some recall, but direct training on this label root
stayed well below the current best model.

This result narrows the path: simply generating more labels from existing
pseudo tracks is not enough. Any further generated-data attempt needs stricter
quality control, lower weighting for generated labels, or human review of the
held-out-like net/center positives before it is likely to push recall above
`0.90`.
