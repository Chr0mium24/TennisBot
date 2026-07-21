# YOLO Final Train Pool ROI+Full Training Result - 2026-07-08

## Scope

This records one retraining pass for the tennis-ball detector and its frozen
final raw benchmark results. It does not validate stereo triangulation,
trajectory prediction, real ROS/chassis, or chassis control.

## Training Setup

- Base model: `artifacts/models/tennis_ball_yolo/model.pt`
- Model family in log: `YOLO26n`, `2,504,190` parameters, `5.8 GFLOPs`
- Pretrained transfer: `708/708` items
- Dataset: `tools/yolo/workspace/runs/final_trainpool_roi_full_20260708`
- Dataset size: `7939` images
- Split: `7156` train, `783` val
- Dataset composition: `1439` full1080, `5000` roi_positive, `1500` roi_negative
- Source split leakage check: `0` source split violations
- Image size: `960`
- Epochs: `35`, early-stopped at epoch `29`
- Best epoch: `21`
- Batch: `32`
- Workers: `0`
- Device: remote `NVIDIA GeForce RTX 5070 Ti`
- CUDA env: `/home/anilam/Downloads/vision/yolo_training/.venv`

The first training attempt used stdin execution with `workers=8`, which failed
because Python multiprocessing tried to import the `<stdin>` module. The
successful retry used `workers=0`.

## Internal Validation

The best internal validation row was epoch `21`:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| 21 | 0.92282 | 0.72884 | 0.76918 | 0.56672 |

This validation set is derived from the train pool and is not the final score.
The final score is the frozen raw-image benchmark below.

## Final Raw Benchmark

Benchmark manifest:
`tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl`

Benchmark size: `381` images, with `72` auto-exposure and `309`
fixed-exposure images. Bucket counts are `small=112`, `medium=35`,
`large=142`, `empty=92`.

### Full Frame, Best Model

`best.pt` was selected by internal validation mAP50-95.

| imgsz | conf | overall R/P | auto R/P | fixed R/P | small R | medium R | large R | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 960 | 0.05 | 0.464 / 0.865 | 1.000 / 0.795 | 0.305 / 0.944 | 0.000 | 0.143 | 0.908 | 2 | 140.16 |
| 960 | 0.25 | 0.450 / 0.935 | 0.970 / 0.877 | 0.296 / 1.000 | 0.000 | 0.114 | 0.887 | 1 | 140.16 |
| 1280 | 0.05 | 0.550 / 0.859 | 1.000 / 0.805 | 0.417 / 0.903 | 0.000 | 0.514 | 0.993 | 2 | 105.37 |
| 1280 | 0.25 | 0.522 / 0.926 | 0.955 / 0.875 | 0.395 / 0.967 | 0.000 | 0.400 | 0.965 | 2 | 105.37 |
| 1536 | 0.05 | 0.581 / 0.824 | 0.970 / 0.780 | 0.466 / 0.852 | 0.000 | 0.800 | 0.986 | 4 | 80.13 |
| 1536 | 0.25 | 0.578 / 0.918 | 0.970 / 0.853 | 0.462 / 0.963 | 0.000 | 0.771 | 0.986 | 2 | 80.13 |

`last.pt` at `imgsz=960` was slightly worse than `best.pt`: at `conf=0.05`,
overall recall/precision was `0.443 / 0.895`, auto was `0.924 / 0.859`,
fixed was `0.300 / 0.931`, small recall was `0.000`, medium recall was
`0.114`, large recall was `0.873`, and estimated stereo FPS was `141.84`.

### Fixed 4-ROI Fallback

This test runs four fixed `1024x576` crops per full frame
top-left/top-right/bottom-left/bottom-right, maps detections back to full-frame
coordinates, and applies confidence-sorted NMS at IoU `0.70`.

| imgsz | conf | overall R/P | small R | medium R | large R | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 960 | 0.05 | 0.270 / 0.453 | 0.000 | 0.057 | 0.535 | 9 | 37.38 |
| 1280 | 0.05 | 0.253 / 0.480 | 0.000 | 0.057 | 0.500 | 9 | 28.91 |
| 1536 | 0.05 | 0.232 / 0.265 | 0.000 | 0.057 | 0.458 | 21 | 22.26 |

This fallback is worse than full-frame. The likely measured failure mode is
crop-boundary truncation: four fixed windows cover the frame, but a ball can be
near a crop edge, so the detector sees a clipped ball and the mapped prediction
does not match the full-frame label at IoU `0.50`. It also misses the `50 FPS`
stereo target.

### Oracle Single ROI

This is an upper-bound test, not a deployable runtime. Positive images use one
`1024x576` crop centered on the ground-truth ball. Empty images use a center
crop.

| imgsz | conf | overall R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 960 | 0.05 | 0.785 / 0.762 | 0.500 / 0.824 | 0.971 / 0.872 | 0.965 / 0.737 | 5 | 144.27 |
| 960 | 0.25 | 0.761 / 0.870 | 0.455 / 0.962 | 0.971 / 0.919 | 0.951 / 0.839 | 2 | 144.27 |
| 1280 | 0.05 | 0.772 / 0.695 | 0.518 / 0.753 | 0.857 / 0.938 | 0.951 / 0.668 | 10 | 113.35 |
| 1280 | 0.25 | 0.744 / 0.833 | 0.509 / 0.919 | 0.743 / 1.000 | 0.930 / 0.800 | 5 | 113.35 |
| 1536 | 0.05 | 0.730 / 0.580 | 0.536 / 0.571 | 0.571 / 0.870 | 0.923 / 0.577 | 9 | 88.11 |
| 1536 | 0.25 | 0.713 / 0.736 | 0.527 / 0.747 | 0.486 / 0.944 | 0.915 / 0.739 | 7 | 88.11 |

Oracle ROI proves that a good locked ROI can recover some small targets while
staying above the FPS target. It does not solve the smallest fixed-exposure
cases: small recall stays around `0.50`.

## Small-Target Inspection

The final benchmark fixed-exposure small targets are much smaller than most
small targets in the train pool.

| split | fixed small count | median max box dim | pct <= 7 px | pct <= 8 px |
|---|---:|---:|---:|---:|
| train_pool | 312 | 10.33 px | 0.154 | 0.266 |
| benchmark | 112 | 6.64 px | 0.786 | 0.964 |

In full-frame mode, those benchmark small boxes are reduced further by model
input scaling:

- Full-frame `imgsz=960`: median small target is about `3.3 px` at model input.
- Full-frame `imgsz=1536`: median small target is about `5.3 px` at model input.
- `1024x576` ROI at `imgsz=960`: median small target is about `6.2 px` at model input.

For oracle `1024x576` ROI at `imgsz=960`, small hit/miss stats at `conf=0.05`
were:

| group | count | max box dim min | median | max |
|---|---:|---:|---:|---:|
| hit | 56 | 5.61 px | 6.74 px | 7.45 px |
| miss | 56 | 4.48 px | 6.18 px | 9.72 px |

The missed small examples had no candidate boxes at all: median best IoU was
`0.0`, median prediction count was `0`. This is detector response failure, not
just a box matching threshold issue.

## Readout

This training pass improved fixed-exposure precision and large/medium recall,
but it does not meet the objective.

- Speed is not the bottleneck for full-frame. `imgsz=1536` still gives about
  `80` estimated stereo FPS and improves fixed medium/large recall.
- Full-frame small recall is `0.000` even at `imgsz=1536`.
- Fixed 4-ROI fallback is not viable with this exact crop plan: it is slower
  than the FPS target and less accurate than full-frame.
- Oracle single ROI is useful but only as a locked-tracker upper bound. It
  reaches about `0.50` small recall, so the current detector still lacks a
  stable response to 5-6 px balls.

Next work should not repeat the same training recipe for more epochs. The data
and/or model need to target the tiny fixed-exposure regime directly:

- Add more fixed-exposure positives whose full-frame max box dimension is
  `4-8 px`, either from real labels or controlled synthesis/downscaling.
- Train/evaluate a locked ROI model where tiny balls appear as the same
  5-7 px input objects seen in the benchmark, plus hard negatives from cloudy
  and fixed backgrounds.
- Consider a detector with a higher-resolution detection head or a two-stage
  heatmap/keypoint model if 5-6 px full-frame targets remain unstable.
- Avoid fixed 4-window fallback without larger overlap or center guarantees;
  the crop-boundary failure is measurable on this benchmark.

