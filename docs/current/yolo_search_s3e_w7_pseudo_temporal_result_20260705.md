# Search-S3e W7 Pseudo Temporal Heatmap Result - 2026-07-05

## Scope

This trains a separate temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate real ROS/chassis, stereo
triangulation, target prediction, or chassis control.

Training was manually stopped after epoch `15` because the best recall did not
exceed S3d and the 7-frame configuration was substantially slower per epoch.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3e_temporal_heatmap_w7_960x540_pseudo989_synth1000_20260705`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Window: `7` frames
- Input: `960x540`
- Sigma: `5.0` px
- Validation radius: `14` px
- Validation token: `20260701_155008`
- Train exclude: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `50`
- Epochs run: `15`
- Batch: `3`
- Synthetic train samples: `1000`
- Positive loss weight: `100`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 2278 | 2080 | 198 |
| train_real | 1278 | 1080 | 198 |
| train_synthetic | 1000 | 1000 | 0 |
| val | 251 | 93 | 158 |

## Best Saved Checkpoint

The saved `best.pt` and `best_recall.pt` point to the same checkpoint.
Console output shows this was epoch `9`, with training loss `0.01566`.

| selection | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| best F1 | 0.70 | 70 | 145 | 23 | 0.753 | 0.326 | 0.455 | 0.753 | 1.78 |
| best recall | 0.70 | 70 | 145 | 23 | 0.753 | 0.326 | 0.455 | 0.753 | 1.78 |

## Epoch Trace

| epoch | recall | precision | F1 | threshold | best-recall selection |
|---:|---:|---:|---:|---:|---:|
| 1 | 0.398 | 0.303 | 0.344 | 0.70 | 0.398 @ 0.70 |
| 2 | 0.527 | 0.363 | 0.430 | 0.70 | 0.559 @ 0.60 |
| 3 | 0.570 | 0.211 | 0.308 | 0.02 | 0.570 @ 0.02 |
| 4 | 0.699 | 0.269 | 0.388 | 0.70 | 0.699 @ 0.70 |
| 5 | 0.602 | 0.258 | 0.361 | 0.70 | 0.602 @ 0.70 |
| 6 | 0.538 | 0.199 | 0.291 | 0.02 | 0.538 @ 0.02 |
| 7 | 0.720 | 0.267 | 0.390 | 0.02 | 0.720 @ 0.02 |
| 8 | 0.677 | 0.251 | 0.366 | 0.02 | 0.677 @ 0.02 |
| 9 | 0.753 | 0.326 | 0.455 | 0.70 | 0.753 @ 0.70 |
| 10 | 0.742 | 0.276 | 0.402 | 0.70 | 0.742 @ 0.70 |
| 11 | 0.538 | 0.199 | 0.291 | 0.02 | 0.538 @ 0.02 |
| 12 | 0.710 | 0.306 | 0.427 | 0.70 | 0.710 @ 0.70 |
| 13 | 0.591 | 0.219 | 0.320 | 0.02 | 0.591 @ 0.02 |
| 14 | 0.720 | 0.286 | 0.410 | 0.70 | 0.720 @ 0.70 |
| 15 | 0.613 | 0.227 | 0.331 | 0.02 | 0.613 @ 0.02 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 7xRGB 960x540 | 24.15 | 20.70 |

## Comparison

| Model | Main change | Best recall | Precision at best recall | Estimated stereo FPS |
|---|---|---:|---:|---:|
| S3c | 5-frame, 500 synthetic positives | 0.699 | 0.283 | 21.42 |
| S3d | 5-frame, 989 pseudo + 500 synthetic positives | 0.774 | 0.327 | 21.48 |
| S3e | 7-frame, 989 pseudo + 1000 synthetic positives | 0.753 | 0.326 | 20.70 |

## Decision

S3e did train successfully as a separate model, but it did not beat S3d.
The extra temporal context and larger synthetic set were not enough to reach
the requested `>0.90` recall, and the training curve remained unstable.

Do not continue this S3e configuration. The next useful step is to improve
pseudo-label quality or add real continuous labels, especially cam2, then train
a cleaner teacher rather than adding more window length.
