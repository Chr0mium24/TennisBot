# YOLO Edge Fidelity/FPS Probe - 2026-07-04

## Question

Find a path that keeps small/far tennis-ball fidelity while improving CPU edge
FPS.

The key concern is that far balls are very small and blurry. Lowering `imgsz`
improves speed but can shrink the ball below useful detector scale.

## Data Inventory

Raw dataset counts:

- Images under `tools/yolo/workspace/dataset/images`: `17,900`
- Label files under `tools/yolo/workspace/dataset/labels`: `1,222`
- Label files with matching images: `693`
- Matched positive label images: `302`
- Matched empty negative label images: `391`
- Matched boxes: `302`
- Positive label files missing matching images: `288`
- Empty label files missing matching images: `241`

Resolutions among matched labeled images:

- `3840x2160`: `561`
- `1920x1080`: `132`

Box size distribution, in original source pixels:

| metric | min | p5 | p10 | p25 | median | p75 | p90 | p95 | max |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| box max side px | 6.94 | 9.26 | 9.72 | 12.86 | 28.91 | 126.39 | 143.61 | 174.22 | 333.53 |
| box min side px | 6.94 | 8.76 | 9.57 | 12.79 | 28.90 | 111.71 | 137.48 | 167.36 | 313.58 |

Small object counts:

- Boxes with max side `<= 16px`: `101 / 302`
- Boxes with max side `<= 10px`: `36 / 302`

Readout: there is real small-object pressure. Many far balls are already under
`16px` in the original 4K frame.

## Current Model

The current packaged `.pt` model is already a nano-scale YOLO detection model:

- Scale: `n`
- Parameters: `2,504,190`
- Strides: `[8, 16, 32]`
- Classes: `tennis_ball`

This means simply moving to a larger architecture may improve recall but will
hurt CPU FPS. A small-object `P2/stride-4` head may help far balls, but it also
adds feature-map cost and needs a separate experiment.

Training from scratch is not recommended with the current matched data:

- Only `302` matched positive images/boxes are available.
- The existing 1000-image and 5000-image runs rely heavily on copy-paste
  augmentation.
- Pretrained nano fine-tuning is the right baseline until more real positive
  4K data is collected.

## Effective Object Size After Resize

Approximate ball max-side size after model resize:

| Mode | imgsz | p10 px | p25 px | median px | boxes <= 5px |
|---|---:|---:|---:|---:|---:|
| full 4K | 640 | 1.62 | 2.14 | 4.82 | 154 |
| full 4K | 960 | 2.43 | 3.21 | 7.23 | 118 |
| full 4K | 1280 | 3.24 | 4.29 | 9.64 | 88 |
| full 4K | 1536 | 3.89 | 5.14 | 11.56 | 71 |
| tile 2048 | 320 | 1.52 | 2.01 | 4.52 | 156 |
| tile 2048 | 512 | 2.43 | 3.21 | 7.23 | 118 |
| tile 2048 | 640 | 3.04 | 4.02 | 9.03 | 101 |
| tile 1536 | 320 | 2.02 | 2.68 | 6.02 | 130 |
| tile 1536 | 512 | 3.24 | 4.29 | 9.64 | 88 |

Readout:

- `tile_2048 imgsz=512` gives about the same object scale as `full_4k imgsz=960`
  but requires more source crops.
- `tile_2048 imgsz=640` gives slightly worse object scale than
  `full_4k imgsz=1280` at similar model-input cost.
- Exhaustive tile is not a free accuracy/FPS win.

## CPU Probe: Full vs Exhaustive Tile

Sample:

- Validation source: `copy_paste_aug_1000_trial_20260703/val.txt`
- Images: `60`
- Positive images: `45`
- Negative images: `15`
- Ground-truth boxes: `45`
- Backend: Ultralytics/PyTorch CPU
- Threads: `10`
- Confidence: `0.05`
- Match IoU: `0.5`

| case | images | gt | TP | FP | FN | recall | precision | missed_pos | median ms/img | p95 ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| full_640 | 60 | 45 | 35 | 66 | 10 | 0.778 | 0.347 | 10 | 24.8 | 25.8 | 20.13 |
| full_960 | 60 | 45 | 36 | 42 | 9 | 0.800 | 0.462 | 9 | 44.6 | 45.9 | 11.20 |
| full_1280 | 60 | 45 | 37 | 71 | 8 | 0.822 | 0.343 | 8 | 78.9 | 85.1 | 6.34 |
| tile2048_320 | 60 | 45 | 25 | 29 | 20 | 0.556 | 0.463 | 20 | 28.3 | 29.8 | 17.65 |
| tile2048_512 | 60 | 45 | 33 | 49 | 12 | 0.733 | 0.402 | 12 | 57.5 | 60.1 | 8.70 |
| tile2048_640 | 60 | 45 | 34 | 45 | 11 | 0.756 | 0.430 | 11 | 82.0 | 91.0 | 6.10 |
| tile1536_320 | 60 | 45 | 29 | 52 | 16 | 0.644 | 0.358 | 16 | 48.3 | 51.9 | 10.35 |
| tile1536_512 | 60 | 45 | 37 | 58 | 8 | 0.822 | 0.389 | 8 | 109.9 | 116.4 | 4.55 |

Readout:

- Exhaustive tile did not beat full-frame at a useful CPU/FPS point.
- `tile1536_512` matched `full_1280` recall but was slower.
- `tile2048_640` had similar speed to `full_1280` but lower recall.
- The fastest reasonable baseline in this probe is `full_640`, but it still
  only estimates to about `20 FPS` for stereo in the PyTorch CPU path.

## CPU Probe: 4K vs Simulated 1080p

This simulates lower-resolution input by downsampling the same frames to
`1920x1080`, then running high `imgsz`.

| case | images | gt | TP | FP | FN | recall | precision | missed_pos | median ms/img | p95 ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 4k_full_imgsz1280 | 60 | 45 | 37 | 71 | 8 | 0.822 | 0.343 | 8 | 78.2 | 80.2 | 6.39 |
| sim_1080p_imgsz1280 | 60 | 45 | 37 | 60 | 8 | 0.822 | 0.381 | 8 | 76.5 | 79.0 | 6.53 |
| sim_1080p_imgsz960 | 60 | 45 | 36 | 35 | 9 | 0.800 | 0.507 | 9 | 44.3 | 48.2 | 11.29 |
| sim_1080p_imgsz640 | 60 | 45 | 35 | 66 | 10 | 0.778 | 0.347 | 10 | 25.2 | 26.2 | 19.86 |

Readout:

- On this small sample, simulated 1080p did not improve speed for the same
  `imgsz`, because model tensor size dominates.
- Lower-resolution capture cannot recover details lost from a tiny blurry ball.
- If the camera can deliver 4K, keep 4K as the source of truth and reduce compute
  downstream with ROI/crop strategy, not by throwing away source pixels early.

## CPU Probe: ONNX Runtime

The packaged ONNX model has fixed input shape `1x3x1280x1280`, so this only
tests `imgsz=1280`.

| backend | imgsz | images | gt | TP | FP | FN | recall | precision | missed_pos | median infer ms/img | median e2e ms/img | p95 e2e | est stereo FPS e2e |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| onnxruntime | 1280 | 60 | 45 | 38 | 75 | 7 | 0.844 | 0.336 | 7 | 63.9 | 70.8 | 73.0 | 7.06 |

Readout:

- ONNX Runtime CPU is slightly faster than the PyTorch/Ultralytics CPU path at
  `1280`, but still far below `30 FPS` stereo.
- The next deployment benchmark should export dynamic or separate `640/960/1280`
  ONNX files, then test OpenVINO and INT8 quantization.

## Answer

Best current direction:

1. Keep 4K camera capture for data fidelity.
2. Do not use exhaustive tile as the default CPU path.
3. Use full-frame low/mid `imgsz` for coarse detection, then sparse ROI tile for
   refinement/tracking.
4. Export CPU-oriented models instead of using PyTorch/Ultralytics for edge:
   ONNX dynamic or fixed-size variants, then OpenVINO/INT8 on the target CPU.
5. Improve source fidelity with camera settings and data collection:
   short exposure, more light, fixed focus, high shutter speed, and more real
   4K far-ball labels.

Recommended next experiment:

- Implement a sparse ROI detector mode:
  - full-frame `imgsz=640` coarse pass;
  - if a high-confidence detection exists, crop one ROI per camera around that
    position in the next frame;
  - run ROI at `imgsz=512` or `640`;
  - fall back to full-frame when tracking is lost.
- Benchmark against current `full_640`, `full_960`, and `full_1280` CPU results.

This is the only path from these probes that can plausibly improve both fidelity
and FPS without relying on a GPU.
