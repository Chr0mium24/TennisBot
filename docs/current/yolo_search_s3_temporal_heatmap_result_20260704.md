# Search-S3 Temporal Heatmap Result - 2026-07-04

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3_temporal_heatmap_20260704`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/labels`
- Window: `3` frames
- Input: `640x360`
- Sigma: `3.0` px
- Validation token: `20260701_155008`
- Train exclude: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `40`
- Batch: `8`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 196 | 98 | 98 |
| val | 255 | 93 | 162 |

Training positives came from the two non-held-out 4K cam1 continuous sequences:

- `20260701_154019_cam1`
- `20260701_155239_cam1`

The older indoor cam1 samples were not used in this run because their frame
numbers step by 5, while this first temporal model requires adjacent frames.

## Best Validation

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 25 | 0.01207 | 0.70 | 43 | 15 | 50 | 0.462 | 0.741 | 0.570 | 0.548 | 1.21 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 3xRGB 640x360 | 9.02 | 55.43 |
| cpu, 10 threads | 3xRGB 640x360 | 172.29 | 2.90 |

## Decision

This is a teacher experiment. It should not be promoted to the CPU runtime.

Compared with Search-S2, the temporal heatmap direction is better supported:
validation F1 reached 0.570 and oracle recall reached 0.548 on the held-out
`155008` labels, while S2 stayed near 0.08 validation recall and 0.18-0.21
held-out replay recall. The CPU latency is far too slow, so the next step is to
use this direction for teacher labeling and then distill or redesign a small
runtime search model only after recall is higher.
