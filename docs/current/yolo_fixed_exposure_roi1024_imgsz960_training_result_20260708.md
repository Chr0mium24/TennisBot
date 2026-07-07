# YOLO Fixed-Exposure 1024x576 ROI ImgSz960 Training Result - 2026-07-08

## Summary

This run reuses the fixed-exposure single-ROI dataset from
`fixed_exposure_roi1024x576_3000_20260708` and changes only the YOLO training
image size from `640` to `960`.

The run completed on `anilam@10.31.151.120` with `batch=40` and stopped early at
epoch 23. Best validation `mAP50-95` was at epoch 13.

This result validates only the YOLO detector training run. It does not validate
ROS/Gazebo, stereo triangulation, trajectory prediction, or chassis control.

## Dataset

Dataset:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_20260708`

Policy:

- Fixed-exposure source images only.
- Every image is a `1024x576` ROI crop.
- No 4K raw images in the training set.
- No current/old 0260701 dataset images.
- No copy-paste samples.
- Cloudy frames are empty-label negative ROI crops.
- Source-grouped validation split.

Counts:

| item | count |
|---|---:|
| total images | `3573` |
| positive ROI images | `3000` |
| empty ROI images | `573` |
| train images | `3208` |
| val images | `365` |
| val positive images | `308` |
| val empty images | `57` |

## Training Setup

Remote run directory:

`/home/anilam/Codes/TennisBot/tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708`

Configuration:

| parameter | value |
|---|---:|
| model seed checkpoint | `artifacts/models/tennis_ball_yolo/model.pt` |
| model architecture | `YOLO26n` |
| image size | `960` |
| batch | `40` |
| requested epochs | `40` |
| completed epochs | `23` |
| early stopping patience | `10` |
| workers | `8` |
| train-time mosaic/mixup/copy-paste/cutmix | `0.0` |
| train-time HSV/geometric/random erasing/auto augment | disabled |

Runtime:

| item | value |
|---|---:|
| completed training time | `0.133 h` |
| final recorded training time | `480.1 s` |
| typical epoch time after startup | `~20.5 s` |
| observed process GPU memory | `~13.6-13.7 GB` |
| observed total GPU memory | `~14.4 / 16.3 GB` |

`batch=40` did not OOM and kept GPU utilization around `92-94%`.

## Validation Metrics

Best checkpoint by `mAP50-95`:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `13` | `0.96482` | `0.80149` | `0.86411` | `0.69921` |

Final recorded epoch:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `23` | `0.96688` | `0.82792` | `0.86426` | `0.69127` |

Highest CSV recall during training:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `18` | `0.95248` | `0.84600` | `0.88132` | `0.68912` |

The run improves `mAP50-95` over the `imgsz=640` single-ROI run
(`0.69921` vs `0.68037`) and improves the best CSV recall observed during
training (`0.84600` vs `0.80489` in the 640 run).

## Threshold Sweep

The saved `best.pt` checkpoint was evaluated with fixed confidence thresholds
on the validation list, using IoU `0.5` matching.

| conf | TP | FP | FN | precision | recall | F1 | neg images with FP |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.01` | `262` | `205` | `46` | `0.561` | `0.851` | `0.676` | `11` |
| `0.03` | `257` | `108` | `51` | `0.704` | `0.834` | `0.764` | `4` |
| `0.05` | `255` | `85` | `53` | `0.750` | `0.828` | `0.787` | `3` |
| `0.10` | `254` | `59` | `54` | `0.812` | `0.825` | `0.818` | `2` |
| `0.15` | `254` | `41` | `54` | `0.861` | `0.825` | `0.842` | `2` |
| `0.25` | `252` | `26` | `56` | `0.906` | `0.818` | `0.860` | `1` |
| `0.30` | `252` | `23` | `56` | `0.916` | `0.818` | `0.864` | `1` |
| `0.50` | `240` | `7` | `68` | `0.972` | `0.779` | `0.865` | `0` |

The `best.pt` threshold sweep is not better than the `imgsz=640` run at low
confidence thresholds. It has higher mAP, but its low-threshold recall is lower
and false positives are higher.

Because later epochs had higher CSV recall, `last.pt` and `epoch20.pt` were also
swept at IoU `0.5`.

`last.pt`:

| conf | TP | FP | FN | precision | recall | F1 | neg images with FP |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.05` | `260` | `64` | `48` | `0.802` | `0.844` | `0.823` | `7` |
| `0.10` | `259` | `42` | `49` | `0.860` | `0.841` | `0.851` | `5` |
| `0.25` | `253` | `17` | `55` | `0.937` | `0.821` | `0.875` | `3` |
| `0.50` | `250` | `8` | `58` | `0.969` | `0.812` | `0.883` | `1` |

`epoch20.pt`:

| conf | TP | FP | FN | precision | recall | F1 | neg images with FP |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.05` | `263` | `83` | `45` | `0.760` | `0.854` | `0.804` | `5` |
| `0.10` | `261` | `48` | `47` | `0.845` | `0.847` | `0.846` | `3` |
| `0.25` | `257` | `26` | `51` | `0.908` | `0.834` | `0.870` | `2` |
| `0.50` | `251` | `11` | `57` | `0.958` | `0.815` | `0.881` | `1` |

For a recall-oriented runtime, `epoch20.pt` around `conf=0.10-0.25` is more
interesting than `best.pt`. It improves recall at moderate thresholds, but still
does not beat the `imgsz=640` best checkpoint at very low confidence.

## Comparison With ImgSz640

| run | checkpoint | conf | precision | recall | FP | FN |
|---|---|---:|---:|---:|---:|---:|
| `imgsz640` | `best.pt` | `0.05` | `0.849` | `0.860` | `47` | `43` |
| `imgsz960` | `best.pt` | `0.05` | `0.750` | `0.828` | `85` | `53` |
| `imgsz960` | `last.pt` | `0.05` | `0.802` | `0.844` | `64` | `48` |
| `imgsz960` | `epoch20.pt` | `0.05` | `0.760` | `0.854` | `83` | `45` |
| `imgsz640` | `best.pt` | `0.25` | `0.940` | `0.818` | `16` | `56` |
| `imgsz960` | `best.pt` | `0.25` | `0.906` | `0.818` | `26` | `56` |
| `imgsz960` | `last.pt` | `0.25` | `0.937` | `0.821` | `17` | `55` |
| `imgsz960` | `epoch20.pt` | `0.25` | `0.908` | `0.834` | `26` | `51` |

## Artifacts

Remote artifacts:

| artifact | path |
|---|---|
| best checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/best.pt` |
| last checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/last.pt` |
| epoch20 checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/epoch20.pt` |
| results CSV | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/results.csv` |
| log | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708.log` |
| best threshold sweep | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/threshold_sweep_iou50.csv` |
| last threshold sweep | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/threshold_sweep_last_iou50.csv` |
| epoch20 threshold sweep | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/threshold_sweep_epoch20_iou50.csv` |

Checkpoint hashes:

| checkpoint | size | SHA256 |
|---|---:|---|
| `best.pt` | `5,398,661 bytes` | `d89cb775ffab8ad6d04a6c9be47c102c8c96b1333a06ef589d6300e73b5d38b8` |
| `last.pt` | `5,398,661 bytes` | `98dcb5fbf035a100760d2dab84d918b257ab4f0a476a111a4e92197e6f839965` |
| `epoch20.pt` | `20,780,610 bytes` | `c005c4859461ac0b436e9075638f45eac027c3c661ece11315b83974a2980d83` |

## Interpretation

Increasing `imgsz` to `960` helps localization and validation mAP, but it does
not fully solve small-ball recall. The best mAP checkpoint is not the best
runtime checkpoint if the goal is recall.

The practical takeaway is:

- use `imgsz960` only if runtime can afford the slower inference;
- evaluate `epoch20.pt` or `last.pt`, not only `best.pt`, for recall-oriented
  runtime tests;
- if far-away balls still matter most, a smaller ROI or a small-object/heatmap
  detector is still likely needed.
