# Search-S3b Temporal Heatmap Result - 2026-07-05

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3b_temporal_heatmap_w5_960x540_20260705`
- Images root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images`
- Labels root: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/labels`
- Window: `5` frames
- Input: `960x540`
- Sigma: `4.0` px
- Validation token: `20260701_155008`
- Train exclude: `20260701_155008`
- Device: `cuda:0`
- Epochs requested: `45`
- Batch: `4`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 240 | 96 | 144 |
| val | 253 | 93 | 160 |

Compared with Search-S3, the 5-frame window removes two endpoint positives
from the train split and two validation endpoint samples. The higher negative
ratio raises the train negative count from 98 to 144.

## Best Validation

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 29 | 0.00749 | 0.70 | 52 | 4 | 41 | 0.559 | 0.929 | 0.698 | 0.613 | 1.95 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.36 | 21.41 |
| cpu, 10 threads | 5xRGB 960x540 | 430.48 | 1.16 |

## Decision

Search-S3b is better than Search-S3 as a teacher candidate, but still not a
runtime model.

| Model | Window | Input | Best recall | Best precision | Best F1 | Oracle recall | GPU est stereo FPS | CPU est stereo FPS |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| S3 | 3 | 640x360 | 0.462 | 0.741 | 0.570 | 0.548 | 55.43 | 2.90 |
| S3b | 5 | 960x540 | 0.559 | 0.929 | 0.698 | 0.613 | 21.41 | 1.16 |

Interpretation:

- Training another model was useful: longer temporal context and higher input
  resolution improved precision, F1, and oracle recall.
- It still does not solve recall. Later epochs reached observed validation
  recall around `0.624`, but with much lower precision, so this is not yet a
  reliable pseudo-label teacher.
- CPU speed is far below runtime needs. S3b should be used offline only.

Next step:

1. Use S3b to generate candidate pseudo-labels from unlabeled continuous
   sequences, then review/filter them.
2. Add more labeled continuous 4K cam1/cam2 positive sequences, especially cam2.
3. After teacher recall is higher, distill a small runtime search model instead
   of running S3b directly.
