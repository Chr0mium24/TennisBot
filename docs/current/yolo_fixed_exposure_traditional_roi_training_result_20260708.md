# YOLO Fixed-Exposure Traditional ROI Training Result - 2026-07-08

## Summary

The fixed-exposure traditional ROI dataset was trained on the remote GPU host
`anilam@10.31.151.120`. Training completed successfully and stopped early at
epoch 31 because validation `mAP50-95` had not improved for 10 epochs.

This result validates only the YOLO detector training run. It does not validate
ROS/Gazebo, stereo triangulation, trajectory prediction, or chassis control.

## Dataset

Dataset package:

`tools/yolo/workspace/runs/fixed_exposure_traditional_roi_3000_20260707.zip`

SHA256:

`f4c3f0b937c5a387f960d1294a3fe0c7ea7bef9552a74347152528b9d9361663`

Dataset policy:

- Fixed-exposure original images only.
- Cloudy no-ball frames kept as raw empty-label negatives.
- Generated samples use traditional ROI crops and photometric/geometric
  augmentation from fixed-exposure positive frames.
- No copy-paste samples.
- No older current/0260701 dataset images.
- ROI crops that would extend outside the source image are skipped instead of
  padded or filled.

Counts:

| item | count |
|---|---:|
| total images | `4688` |
| positive images | `4115` |
| empty images | `573` |
| boxes | `4115` |
| train images | `4212` |
| val images | `476` |
| generated traditional ROI images | `3000` |

## Training Setup

Remote repo:

`/home/anilam/Codes/TennisBot`

Run directory:

`/home/anilam/Codes/TennisBot/tools/yolo/workspace/runs/training/fixed_exposure_traditional_roi_3000_imgsz1280_batch16_20260707`

Environment:

| item | value |
|---|---|
| GPU | `NVIDIA GeForce RTX 5070 Ti` |
| VRAM | `16.3 GB` |
| Python | `3.12.13` |
| PyTorch | `2.11.0+cu128` |
| Ultralytics | `8.4.90` |

Training configuration:

| parameter | value |
|---|---:|
| model seed checkpoint | `artifacts/models/tennis_ball_yolo/model.pt` |
| model architecture | `YOLO26n` |
| image size | `1280` |
| batch | `16` |
| requested epochs | `40` |
| completed epochs | `31` |
| early stopping patience | `10` |
| workers | `8` |
| train-time mosaic/mixup/copy-paste/cutmix | `0.0` |
| train-time HSV/geometric/random erasing/auto augment | disabled |

Runtime:

| item | value |
|---|---:|
| completed training time | `0.437 h` |
| typical epoch time | `~50.5 s` |
| training GPU memory | `~10.4 GB` |
| observed GPU utilization during training | `~89-93%` |

## Final Metrics

Best checkpoint was selected at epoch 21:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `21` | `0.92617` | `0.75935` | `0.78404` | `0.61288` |

Final recorded epoch:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `31` | `0.94990` | `0.74818` | `0.77189` | `0.60696` |

The final validation line for the saved best checkpoint was:

| class | images | instances | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| `all` | `476` | `413` | `0.924` | `0.758` | `0.784` | `0.613` |

## Artifacts

Remote artifacts:

| artifact | path |
|---|---|
| best checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_traditional_roi_3000_imgsz1280_batch16_20260707/weights/best.pt` |
| last checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_traditional_roi_3000_imgsz1280_batch16_20260707/weights/last.pt` |
| results CSV | `tools/yolo/workspace/runs/training/fixed_exposure_traditional_roi_3000_imgsz1280_batch16_20260707/results.csv` |
| log | `tools/yolo/workspace/runs/training/fixed_exposure_traditional_roi_3000_imgsz1280_batch16_20260707.log` |

Best checkpoint:

| item | value |
|---|---|
| size | `5,448,005 bytes` |
| mtime | `2026-07-08 00:06:10 +0800` |
| SHA256 | `511c844f3ddf5acebf8f8b3d71d108e91714632e751946a2c654c507a1f5c110` |

## Interpretation

The fixed-exposure ROI-only dataset reached a better validation score than the
first early epochs and then plateaued. The best checkpoint should be used for
runtime testing, but this result still needs sequence-level validation under the
ROI search runtime before it can be treated as an operational improvement.
