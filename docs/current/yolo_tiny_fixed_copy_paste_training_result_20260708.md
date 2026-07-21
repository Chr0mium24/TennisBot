# YOLO Tiny Fixed Copy-Paste Training Result - 2026-07-08

## Scope

This records the tiny fixed-exposure copy-paste training pass and its frozen
final raw benchmark results. It does not validate stereo triangulation,
trajectory prediction, real ROS/chassis, or chassis control.

## Dataset

Output root:
`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708`

The dataset was generated only from the final raw benchmark `train_pool`.

| item | count |
|---|---:|
| total images | 13939 |
| train images | 12549 |
| val images | 1390 |
| full1080 | 1439 |
| roi_positive | 5000 |
| roi_negative | 1500 |
| tiny_positive | 6000 |

Validation checks:

- source split violations: `0`
- missing outputs: `0`
- bad labels: `0`
- tiny max dimension: min `4.0`, p25 `5.0`, median `6.0`, p75 `7.0`, max `9.0`
- tiny labels outside `3.5-8.5 px`: `28 / 6000`

## Training

- Start model: `tools/yolo/workspace/runs/training/final_trainpool_roi_full_imgsz960_batch32_20260708/weights/best.pt`
- Dataset: `tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml`
- Image size: `960`
- Batch: `32`
- Epochs: `35`
- Patience: `8`
- Workers: `0`
- Device: remote `NVIDIA GeForce RTX 5070 Ti`
- CUDA env: `/home/anilam/Downloads/vision/yolo_training/.venv`

Training early-stopped at epoch `30`. Best internal validation result was epoch
`22`:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| 22 | 0.88248 | 0.64250 | 0.67123 | 0.40745 |

The internal validation score is lower than the previous ROI+full run. That is
expected to some degree because this dataset has many very small synthetic
targets, but the final raw benchmark below is the deciding metric.

## Final Raw Benchmark - Full Frame

Model:
`tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_imgsz960_batch32_20260708/weights/best.pt`

Benchmark:
`tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl`

| imgsz | conf | overall R/P | auto R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 960 | 0.05 | 0.481 / 0.858 | 0.985 / 0.844 | 0.332 / 0.871 | 0.000 / n/a | 0.257 / 0.750 | 0.915 / 0.903 | 5 | 140.34 |
| 960 | 0.25 | 0.443 / 0.962 | 0.864 / 0.934 | 0.318 / 0.986 | 0.000 / n/a | 0.229 / 1.000 | 0.845 / 0.984 | 3 | 140.34 |
| 1280 | 0.05 | 0.550 / 0.552 | 0.970 / 0.547 | 0.426 / 0.556 | 0.009 / 0.024 | 0.571 / 0.870 | 0.972 / 0.726 | 30 | 105.28 |
| 1280 | 0.25 | 0.529 / 0.674 | 0.939 / 0.674 | 0.408 / 0.674 | 0.009 / 0.034 | 0.486 / 0.895 | 0.951 / 0.828 | 16 | 105.28 |
| 1536 | 0.05 | 0.616 / 0.459 | 0.970 / 0.421 | 0.511 / 0.483 | 0.080 / 0.200 | 0.829 / 0.558 | 0.986 / 0.560 | 33 | 80.09 |
| 1536 | 0.25 | 0.592 / 0.500 | 0.894 / 0.447 | 0.502 / 0.533 | 0.071 / 0.200 | 0.800 / 0.596 | 0.951 / 0.611 | 29 | 80.09 |

`last.pt` at `imgsz=1536` was not better. At `conf=0.05`, small recall was
`0.062`, fixed recall was `0.475`, and estimated stereo FPS was `79.80`.

## Oracle ROI Check

This is an upper bound, not a deployable runtime: one `1024x576` crop centered
on the ground-truth ball for positive images, center crop for empty images.

| imgsz | conf | overall R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 960 | 0.05 | 0.792 / 0.722 | 0.527 / 0.766 | 0.943 / 0.846 | 0.965 / 0.778 | 25 | 143.77 |
| 960 | 0.25 | 0.761 / 0.849 | 0.518 / 0.879 | 0.886 / 0.939 | 0.923 / 0.879 | 11 | 143.77 |
| 1536 | 0.05 | 0.696 / 0.510 | 0.500 / 0.583 | 0.486 / 0.708 | 0.901 / 0.598 | 60 | 87.82 |
| 1536 | 0.25 | 0.640 / 0.734 | 0.455 / 0.810 | 0.400 / 0.875 | 0.845 / 0.789 | 21 | 87.82 |

The previous model's oracle `1024x576 @ imgsz960` small recall was about
`0.500`. This run reaches only `0.527`. The improvement is too small to explain
the full-frame failure as just a runtime crop issue.

## Readout

This model still does not meet the objective.

- The best full-frame result is `imgsz=1536, conf=0.05`: overall recall
  `0.616`, fixed recall `0.511`, small recall `0.080`, estimated stereo FPS
  `80.09`.
- Speed remains above `50 FPS`, so runtime is not the limiting factor.
- Tiny copy-paste improved full-frame small recall from `0.000` to only
  `0.080`, while adding many false positives.
- Oracle ROI small recall stayed around `0.52`, so the detector still does not
  reliably respond to real 5-7 px fixed-exposure balls.

The evidence points to a representation/model limitation and a synthetic-real
appearance mismatch, not just a lack of tiny-labeled samples. The next useful
step should not be more rectangular tiny copy-paste at the same model head.

Recommended next experiments:

- Collect or label more real fixed-exposure frames where the ball is `4-8 px`.
- Try a detector variant with a smaller-stride/high-resolution detection head,
  or a heatmap/keypoint model trained directly on ball centers.
- Use temporal evidence: integrate consecutive-frame ROI/track scoring before
  declaring a miss, since a single 5-6 px frame is near the detector limit.
- If synthetic data is used again, generate it from real fixed-exposure
  point-spread/blur statistics instead of simple alpha copy-paste.

