# YOLO Tiny P2 No-P5 Final Trainpool Plan - 2026-07-08

## Goal

Train a P2-head YOLO candidate on the current final trainpool tiny dataset to
check whether a stride-4 head improves the fixed-exposure tiny-ball recall that
the current promoted P3/P4/P5 model misses.

This is a detector training/evaluation experiment only. It does not validate
stereo triangulation, trajectory prediction, real ROS/chassis, or chassis control.

## Candidate

Config:

`tools/yolo/configs/tennis_yolo26_tiny_p2_no_p5.yaml`

Architecture summary on the remote training host:

| item | value |
|---|---:|
| detect heads | `P2/P3/P4` |
| strides | `4, 8, 16` |
| parameters | `649,466` |
| purpose | preserve high-resolution small-object features while dropping P5 large-object compute |

Pretrained transfer from the current runtime package was tested with:

```python
from ultralytics import YOLO

model = YOLO("tools/yolo/configs/tennis_yolo26_tiny_p2_no_p5.yaml")
model.load("artifacts/models/tennis_ball_yolo/model.pt")
```

Result: `70/774` items transferred. This means the experiment should be treated
as mostly new-architecture training rather than a full fine-tune of the current
promoted detector.

## Current Dataset

Remote dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708`

This dataset was generated from the frozen final raw benchmark train pool.

| item | count |
|---|---:|
| total images | `13,939` |
| train images | `12,549` |
| val images | `1,390` |
| full1080 | `1,439` |
| roi_positive | `5,000` |
| roi_negative | `1,500` |
| tiny_positive | `6,000` |
| fixed-exposure source samples | `13,783` |
| auto-exposure source samples | `156` |

Source bucket counts:

| bucket | count |
|---|---:|
| empty | `8,004` |
| small | `3,244` |
| medium | `1,864` |
| large | `827` |

Label max-dimension distribution in output pixels:

| group | n | min | p25 | median | p75 | max | <=8 px | <=10 px |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| all labels | `11,935` | `2.48` | `6.00` | `7.15` | `13.89` | `246.86` | `6,389` | `7,739` |
| full1080 | `935` | `2.48` | `6.40` | `15.25` | `55.12` | `246.86` | `312` | `374` |
| roi_positive | `5,000` | `4.95` | `9.70` | `13.91` | `29.63` | `246.86` | `773` | `1,365` |
| tiny_positive | `6,000` | `4.00` | `5.00` | `6.00` | `7.00` | `9.00` | `5,304` | `6,000` |
| train split | `10,749` | `2.48` | `6.00` | `7.16` | `13.84` | `246.86` | `5,708` | `6,924` |
| val split | `1,186` | `2.96` | `6.00` | `7.00` | `14.12` | `186.60` | `681` | `815` |

## Training Plan

Run on `anilam@10.31.151.120` using the existing training venv:

`/home/anilam/Downloads/vision/yolo_training/.venv`

Remote environment checked before training:

| item | value |
|---|---|
| GPU | `NVIDIA GeForce RTX 5070 Ti` |
| VRAM | `16,303 MiB` |
| PyTorch | `2.11.0+cu128` |
| Ultralytics | `8.4.53` |

Training command:

```bash
cd /home/anilam/Codes/TennisBot
/home/anilam/Downloads/vision/yolo_training/.venv/bin/yolo detect train \
  model=tools/yolo/configs/tennis_yolo26_tiny_p2_no_p5.yaml \
  data=tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml \
  pretrained=artifacts/models/tennis_ball_yolo/model.pt \
  imgsz=960 \
  epochs=35 \
  patience=8 \
  batch=32 \
  device=0 \
  workers=8 \
  project=tools/yolo/workspace/runs/training \
  name=final_trainpool_tiny_p2_no_p5_imgsz960_batch32_20260708 \
  exist_ok=True \
  seed=20260708 \
  deterministic=True \
  save=True \
  save_period=10 \
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

## Evaluation Plan

After training, evaluate at least:

- internal validation best epoch from `results.csv`;
- threshold sweep on the model's val split if practical;
- frozen final raw benchmark at `imgsz=960,1280,1536`, `conf=0.05,0.25`;
- compare against the current promoted tiny copy-paste model:
  - best full-frame row: `imgsz=1536`, `conf=0.05`;
  - overall recall `0.616`;
  - fixed-exposure recall `0.511`;
  - small recall `0.080`;
  - estimated stereo FPS `80.09`.

Success is not judged by internal mAP alone. The useful signal is whether the
P2 candidate improves final raw small/fixed recall without destroying precision
or falling below the estimated stereo FPS target.
