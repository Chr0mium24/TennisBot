# YOLO Fixed-Exposure 1024x576 ROI Training Result - 2026-07-08

## Summary

This run tests a single runtime-matched ROI distribution: every training and
validation image is a `1024x576` crop from the fixed-exposure 4K source frames.
No 4K raw images, current/old dataset images, or copy-paste samples are included.

The detector trained successfully on `anilam@10.31.151.120` and stopped early at
epoch 33. Best validation `mAP50-95` was at epoch 23.

This result validates only the YOLO detector training run. It does not validate
ROS/Gazebo, stereo triangulation, trajectory prediction, or chassis control.

## Dataset

Dataset directory:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_20260708`

Zip package:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_20260708.zip`

Zip SHA256:

`86444c2d343fc2e17f860dced83c6ca0a5daee9c972497d55029c87cba27157a`

Dataset policy:

- Fixed-exposure source images only.
- Single ROI size: `1024x576`.
- No `3840x2160` raw images in the training set.
- No current/old 0260701 dataset images.
- No copy-paste samples.
- Cloudy frames are used only as empty-label negative ROI crops.
- ROI crop windows are clamped inside the source frame; no crop-boundary padding
  or fill is used.
- Validation split is source-grouped, so ROI crops derived from the same 4K
  source image do not appear in both train and val.

Counts:

| item | count |
|---|---:|
| source images | `1688` |
| source positive images | `1115` |
| source empty images | `573` |
| source cloudy empty images | `483` |
| ROI positive images | `3000` |
| ROI empty images | `573` |
| total images | `3573` |
| train images | `3208` |
| val images | `365` |
| val positive images | `308` |
| val empty images | `57` |

Kind counts:

| kind | count |
|---|---:|
| `roi_positive_base` | `1115` |
| `roi_positive_aug` | `1885` |
| `roi_negative_cloudy` | `483` |
| `roi_negative_fixed_empty` | `90` |

## Training Setup

Remote repo:

`/home/anilam/Codes/TennisBot`

Run directory:

`/home/anilam/Codes/TennisBot/tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708`

Configuration:

| parameter | value |
|---|---:|
| model seed checkpoint | `artifacts/models/tennis_ball_yolo/model.pt` |
| model architecture | `YOLO26n` |
| image size | `640` |
| batch | `64` |
| requested epochs | `40` |
| completed epochs | `33` |
| early stopping patience | `10` |
| workers | `8` |
| train-time mosaic/mixup/copy-paste/cutmix | `0.0` |
| train-time HSV/geometric/random erasing/auto augment | disabled |

Runtime:

| item | value |
|---|---:|
| final recorded training time | `329.1 s` |
| typical epoch time after startup | `~9.7 s` |
| observed GPU memory | `~9.8 GB` |

Note: the `tee` log file did not land in the expected path for this run. The
Ultralytics run directory, `results.csv`, saved weights, and threshold sweep CSVs
are present.

## Validation Metrics

Best checkpoint by `mAP50-95`:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `23` | `0.96588` | `0.78571` | `0.84060` | `0.68037` |

Final recorded epoch:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| `33` | `0.95773` | `0.78896` | `0.82613` | `0.66965` |

Compared with the previous mixed 4K/multi-ROI run, this run is much faster and
has better `mAP50-95`, but the CSV recall is still not high enough for a
catching runtime. The validation split is also stricter here because it is
source-grouped.

## Threshold Sweep

The saved best checkpoint was evaluated on the validation list with fixed
confidence thresholds. Detection-level matching uses IoU `0.5`.

| conf | TP | FP | FN | precision | recall | F1 | neg images with FP |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.01` | `269` | `141` | `39` | `0.656` | `0.873` | `0.749` | `4` |
| `0.03` | `267` | `72` | `41` | `0.788` | `0.867` | `0.825` | `3` |
| `0.05` | `265` | `47` | `43` | `0.849` | `0.860` | `0.855` | `2` |
| `0.08` | `262` | `37` | `46` | `0.876` | `0.851` | `0.863` | `2` |
| `0.10` | `260` | `30` | `48` | `0.897` | `0.844` | `0.870` | `2` |
| `0.15` | `260` | `26` | `48` | `0.909` | `0.844` | `0.875` | `2` |
| `0.20` | `256` | `20` | `52` | `0.928` | `0.831` | `0.877` | `2` |
| `0.25` | `252` | `16` | `56` | `0.940` | `0.818` | `0.875` | `2` |
| `0.30` | `248` | `12` | `60` | `0.954` | `0.805` | `0.873` | `1` |
| `0.40` | `244` | `9` | `64` | `0.964` | `0.792` | `0.870` | `0` |
| `0.50` | `241` | `7` | `67` | `0.972` | `0.782` | `0.867` | `0` |

The IoU `0.3` sweep is nearly identical to IoU `0.5`, so the remaining misses
are mostly not just slightly mislocalized boxes. Many are not detected with a
usable candidate even at very low confidence.

## Miss Analysis

At `conf=0.01` and IoU `0.5`, the best checkpoint still misses `39 / 308`
positive validation ROI images.

Miss distribution:

| category | count |
|---|---:|
| `roi_positive_aug` misses | `34` |
| `roi_positive_base` misses | `5` |
| session `20260707_141324` misses | `19` |
| session `20260707_140926` misses | `7` |
| session `20260707_141056` misses | `5` |
| other sessions | `8` |

The missed balls are much smaller than the hits:

| group | average box width | average box height |
|---|---:|---:|
| missed positives | `19.3 px` | `19.7 px` |
| hit positives | `51.1 px` | `51.5 px` |

Several missed validation samples have labels only `5-10 px` wide in the
`1024x576` ROI. After `imgsz=640` resizing, these are roughly `3-6 px` targets
inside the network input, which is below the reliable range for this detector.

## Artifacts

Remote artifacts:

| artifact | path |
|---|---|
| best checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/weights/best.pt` |
| last checkpoint | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/weights/last.pt` |
| results CSV | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/results.csv` |
| threshold sweep IoU 0.5 | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/threshold_sweep_iou50.csv` |
| threshold sweep IoU 0.3 | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz640_batch64_20260708/threshold_sweep_iou30.csv` |

Best checkpoint:

| item | value |
|---|---|
| size | `5,361,157 bytes` |
| SHA256 | `72bd48ba2e556bea7d356c6840eb31d7a3667334e56712be0187149a078380a5` |

## Interpretation

The single `1024x576` ROI distribution is better aligned with the proposed
runtime and trains much faster than the mixed 4K/multi-ROI run. It improves the
validation score, but recall is still limited by very small held-out balls.

For runtime testing, `conf=0.05-0.10` is a better starting range than `0.25` if
recall is the priority. For the tiny-ball misses, the next detector-side options
are:

- keep `1024x576` ROI but train/infer at a larger `imgsz` such as `960`;
- reduce the single ROI size, for example to `640x360`, if tracking can keep the
  ball near the ROI center;
- use a small-object architecture/head or heatmap-style detector for the early
  far-away ball stage.
