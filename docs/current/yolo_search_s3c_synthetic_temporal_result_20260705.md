# Search-S3c Synthetic Temporal Heatmap Result - 2026-07-05

## Scope

This trains a small temporal heatmap teacher for search/acquisition.
It uses labeled image sequences only and does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Settings

- Output: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/temporal_heatmap/search_s3c_temporal_heatmap_w5_960x540_synth500_20260705`
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
- Synthetic train samples: `500`

## Data

| split | samples | positives | negatives |
|---|---:|---:|---:|
| train | 740 | 596 | 144 |
| train_real | 240 | 96 | 144 |
| train_synthetic | 500 | 500 | 0 |
| val | 253 | 93 | 160 |

## Best Validation

This training run was produced before the trainer saved a separate
`best_recall.pt`. The saved `best.pt` is the best-F1 checkpoint. During training,
the highest observed validation recall was `0.731` at epoch 21, with precision
`0.504` and F1 `0.596`.

Post-hoc recall-threshold evaluation on saved checkpoints:

| checkpoint | selected by | threshold | TP | FP | FN | recall | precision | F1 | oracle recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| best.pt | F1 | 0.70 | 62 | 19 | 31 | 0.667 | 0.765 | 0.713 | 0.699 |
| best.pt | recall | 0.30 | 65 | 165 | 28 | 0.699 | 0.283 | 0.402 | 0.699 |
| last.pt | F1/recall | 0.70 | 64 | 77 | 29 | 0.688 | 0.454 | 0.547 | 0.688 |

So the saved checkpoints do not reach `0.90` recall even under recall-first
threshold selection.

| epoch | loss | threshold | TP | FP | FN | recall | precision | F1 | oracle recall | mean TP dist px |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 11 | 0.00755 | 0.70 | 62 | 19 | 31 | 0.667 | 0.765 | 0.713 | 0.699 | 1.42 |

## Latency

| device | input | median ms/frame | estimated stereo FPS |
|---|---|---:|---:|
| cuda:0 | 5xRGB 960x540 | 23.34 | 21.42 |
| cpu, 10 threads | 5xRGB 960x540 | 439.19 | 1.14 |

## Decision

Search-S3c improves recall, but it does not reach the requested `>0.90` recall.

| Model | Extra data | Best-F1 recall | Best precision | Best F1 | Highest observed recall | Oracle recall |
|---|---|---:|---:|---:|---:|---:|
| S3 | none | 0.462 | 0.741 | 0.570 | 0.570 | 0.548 |
| S3b | none | 0.559 | 0.929 | 0.698 | 0.624 | 0.613 |
| S3c | 500 synthetic positives | 0.667 | 0.765 | 0.713 | 0.731 | 0.699 |

The synthetic temporal data is useful: best-F1 recall improved from `0.559` to
`0.667`, and the highest observed recall improved to `0.731`. However, the
remaining gap to `0.90` is still large. More synthetic positives alone are not
enough yet; the aborted `synthetic-count=2000` run showed much slower training
and poor first-epoch precision/recall.

This model remains offline-only. CPU speed is far below runtime needs.

## Next Step

The trainer has now been updated to save both:

- `best.pt` for best F1;
- `best_recall.pt` for the highest recall validation checkpoint.

The next training run should optimize and inspect `best_recall.pt`, then use the
high-recall teacher to mine pseudo-labels from unlabeled continuous sequences.
To get past 90% recall, the project likely needs more reviewed real continuous
cam1/cam2 positives in addition to synthetic data.
