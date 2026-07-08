# YOLO Low-Light Domain Match Plan - 2026-07-09

## Question

Test whether low-level image processing can make the detector's training domain
and test-time domain better aligned for fixed-exposure tiny tennis balls.

The idea is reasonable only if the same preprocessing is applied at both train
and runtime/evaluation. Training-only dark/light augmentation can improve
robustness, but it does not by itself make the deployed image domain match the
training domain.

This is a detector-only experiment. It does not validate stereo triangulation,
trajectory prediction, ROS/Gazebo, or chassis control.

## Hypothesis

The current fixed-exposure small-ball misses may be partly caused by low local
contrast and dark/noisy backgrounds. A conservative low-light enhancement pass
could make the ball edge and color more separable before YOLO resizing.

Risk: enhancing 4-8px objects also amplifies texture, compression artifacts, and
cloudy background noise, so false positives may rise.

## Transform

Use one deterministic transform for both the trainset copy and benchmark copy:

1. Apply CLAHE on the LAB `L` channel with clip limit `2.0` and tile grid `8x8`.
2. Apply gamma brightening with `gamma=0.75`.

The image size and labels stay unchanged.

## Experiment

Remote host:

`anilam@10.31.151.120`

Base dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708`

Base model:

`runs/detect/tools/yolo/workspace/runs/training/final_trainpool_tiny_p2_no_p5_imgsz960_batch32_20260708/weights/best.pt`

Generated dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_20260709`

Generated benchmark:

`tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709`

Run order:

1. Generate a low-light-enhanced copy of the final trainpool tiny dataset.
2. Generate a low-light-enhanced copy of the frozen final raw benchmark images.
3. Evaluate the existing P2 `best.pt` on the enhanced benchmark. This isolates
   test-time preprocessing.
4. Continue training from the P2 `best.pt` on the enhanced trainset.
5. Evaluate the continued model on the enhanced benchmark.

## Training Command

```bash
cd /home/anilam/Codes/TennisBot
/home/anilam/Downloads/vision/yolo_training/.venv/bin/yolo detect train \
  model=runs/detect/tools/yolo/workspace/runs/training/final_trainpool_tiny_p2_no_p5_imgsz960_batch32_20260708/weights/best.pt \
  data=tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_20260709/data.yaml \
  imgsz=960 \
  epochs=18 \
  patience=6 \
  batch=32 \
  device=0 \
  workers=8 \
  project=tools/yolo/workspace/runs/training \
  name=final_trainpool_tiny_p2_no_p5_lowlight_g075_clahe2_imgsz960_batch32_20260709 \
  exist_ok=True \
  seed=20260709 \
  deterministic=True \
  save=True \
  save_period=6 \
  cache=False \
  plots=False \
  mosaic=0.0 \
  mixup=0.0 \
  copy_paste=0.0 \
  cutmix=0.0 \
  auto_augment=None \
  erasing=0.0 \
  hsv_h=0.0 \
  hsv_s=0.0 \
  hsv_v=0.0 \
  degrees=0.0 \
  translate=0.0 \
  scale=0.0 \
  shear=0.0 \
  perspective=0.0 \
  flipud=0.0 \
  fliplr=0.0
```

## Success Signal

Compare at `imgsz=1536` on the enhanced frozen benchmark:

- existing P2 `best.pt` with preprocessing;
- continued low-light-trained `best.pt` with preprocessing;
- previous original-domain P2 result: small recall `0.232` at `conf=0.05` and
  `0.143` at `conf=0.25`.

The experiment is useful if small/fixed recall improves without unacceptable
empty-frame false positives. It should not be promoted unless the preprocessing
is wired into runtime and evaluated there as well.
