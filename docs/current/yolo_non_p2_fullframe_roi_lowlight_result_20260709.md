# YOLO Non-P2 Full-Frame and ROI Low-Light Result - 2026-07-09

## Scope

This records the non-P2 low-light domain-match experiment requested after
stopping the P2 direction. It covers:

- the current non-P2 full-frame YOLO26n checkpoint;
- the existing fixed-exposure 1024x576 ROI YOLO26n checkpoint;
- deterministic train/test preprocessing with LAB CLAHE plus gamma brightening.

This is detector-only. It does not validate stereo triangulation, trajectory
prediction, ROS/Gazebo, or chassis control.

## Transform

The transform was identical for train and eval images:

1. LAB `L` channel CLAHE, clip limit `2.0`, grid `8x8`.
2. Gamma brightening, `gamma=0.75`.

## Datasets

Full-frame enhanced dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_20260709`

| item | count |
|---|---:|
| total images | 13939 |
| train images | 12549 |
| val images | 1390 |
| full1080 | 1439 |
| roi_positive | 5000 |
| roi_negative | 1500 |
| tiny_positive | 6000 |

Enhanced frozen raw benchmark:

`tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709`

| item | count |
|---|---:|
| benchmark images | 381 |
| auto exposure | 72 |
| fixed exposure | 309 |
| small targets | 112 |
| medium targets | 35 |
| large targets | 142 |
| empty images | 92 |

ROI enhanced dataset:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_20260709`

| item | count |
|---|---:|
| total images | 3573 |
| train images | 3208 |
| val images | 365 |
| positive ROI images | 3000 |
| empty ROI images | 573 |
| val positive images | 308 |
| val empty images | 57 |

Implementation note: the ROI enhanced dataset initially kept relative
`train.txt` and `val.txt` paths. Ultralytics resolved those incorrectly when
called with an absolute `data.yaml`, so the train lists were rewritten as
`train_abs.txt` and `val_abs.txt`.

## Full-Frame Training

Seed checkpoint:

`tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_imgsz960_batch32_20260708/weights/best.pt`

Low-light run:

`tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_imgsz960_batch32_20260709`

Settings:

| parameter | value |
|---|---:|
| architecture | non-P2 YOLO26n, P3/P4/P5 |
| transferred weights | 708 / 708 |
| imgsz | 960 |
| batch | 32 |
| requested epochs | 18 |
| completed epochs | 8 |
| patience | 6 |
| workers | 8 |
| train-time HSV/geometric/mosaic/mixup/copy-paste | disabled |

Internal validation:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| 2 | 0.82875 | 0.60455 | 0.64174 | 0.38509 |
| 6 | 0.81669 | 0.60961 | 0.64768 | 0.38187 |
| 8 | 0.85636 | 0.60322 | 0.63325 | 0.38191 |

Epoch 2 was the best internal mAP50-95 checkpoint. Epoch 6 had the highest
internal recall, so both `best.pt` and `epoch6.pt` were checked on the frozen
benchmark.

## Full-Frame Frozen Benchmark

All rows use the enhanced frozen raw benchmark at `imgsz=1536`.

| model | conf | overall R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| original-domain baseline | 0.05 | 0.616 / 0.459 | 0.511 / 0.483 | 0.080 / 0.200 | 0.829 / 0.558 | 0.986 / 0.560 | 33 | 80.09 |
| test-time lowlight only | 0.05 | 0.581 / 0.499 | 0.484 / 0.414 | 0.062 / 0.115 | 0.743 / 0.481 | 0.951 / 0.767 | 38 | 79.00 |
| lowlight `best.pt` | 0.05 | 0.592 / 0.572 | 0.480 / 0.514 | 0.009 / 0.033 | 0.857 / 0.698 | 0.986 / 0.795 | 36 | 78.99 |
| lowlight `last.pt` | 0.05 | 0.609 / 0.611 | 0.498 / 0.587 | 0.036 / 0.100 | 0.886 / 0.861 | 0.993 / 0.792 | 26 | 79.35 |
| lowlight `epoch6.pt` | 0.05 | 0.616 / 0.426 | 0.502 / 0.367 | 0.045 / 0.068 | 0.886 / 0.525 | 1.000 / 0.664 | 52 | 79.04 |
| original-domain baseline | 0.25 | 0.592 / 0.500 | 0.502 / 0.533 | 0.071 / 0.200 | 0.800 / 0.596 | 0.951 / 0.611 | 29 | 80.09 |
| test-time lowlight only | 0.25 | 0.536 / 0.574 | 0.466 / 0.486 | 0.054 / 0.128 | 0.657 / 0.548 | 0.887 / 0.846 | 28 | 79.00 |
| lowlight `best.pt` | 0.25 | 0.561 / 0.726 | 0.453 / 0.682 | 0.000 / 0.000 | 0.743 / 0.867 | 0.958 / 0.901 | 26 | 78.99 |
| lowlight `last.pt` | 0.25 | 0.599 / 0.698 | 0.484 / 0.684 | 0.027 / 0.100 | 0.829 / 1.000 | 0.993 / 0.844 | 20 | 79.35 |
| lowlight `epoch6.pt` | 0.25 | 0.595 / 0.526 | 0.484 / 0.468 | 0.036 / 0.075 | 0.800 / 0.560 | 0.986 / 0.769 | 36 | 79.04 |

Full-frame readout:

- Test-time lowlight alone reduced overall, fixed, and small recall.
- Domain-matched lowlight training did not recover small-object recall.
- `epoch6.pt` matched original overall recall at `conf=0.05`, but only by
  increasing false positives; small recall was still worse (`0.045` vs `0.080`).
- No full-frame lowlight checkpoint should be promoted.

## ROI Baseline

Seed checkpoint:

`tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/epoch20.pt`

Original-domain reference from the previous ROI result:

| conf | precision | recall | FP | FN | neg images with FP |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.760 | 0.854 | 83 | 45 | 5 |
| 0.10 | 0.845 | 0.847 | 48 | 47 | 3 |
| 0.25 | 0.908 | 0.834 | 26 | 51 | 2 |
| 0.50 | 0.958 | 0.815 | 11 | 57 | 1 |

Same checkpoint, enhanced ROI val only:

| conf | precision | recall | FP | FN | neg images with FP |
|---:|---:|---:|---:|---:|---:|
| 0.05 | 0.699 | 0.786 | 104 | 66 | 11 |
| 0.10 | 0.763 | 0.773 | 74 | 70 | 7 |
| 0.25 | 0.870 | 0.760 | 35 | 74 | 5 |
| 0.50 | 0.941 | 0.727 | 14 | 84 | 1 |

So test-time lowlight alone clearly hurt ROI recall and false positives.

## ROI Training

The first ROI fine-tune used `optimizer=auto`, AMP enabled, and `workers=0`
after fixing path handling. It became invalid at epoch 3 because the losses
turned into `nan`. That run was stopped and not used for the result.

Stable ROI run:

`tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_imgsz960_batch40_lr2e4_noamp_20260709`

Settings:

| parameter | value |
|---|---:|
| architecture | non-P2 YOLO26n, P3/P4/P5 |
| transferred weights | 708 / 708 |
| imgsz | 960 |
| batch | 40 |
| requested epochs | 20 |
| completed epochs | 14 |
| patience | 8 |
| workers | 0 |
| optimizer | AdamW |
| lr0 | 0.0002 |
| lrf | 0.1 |
| AMP | false |
| train-time HSV/geometric/mosaic/mixup/copy-paste | disabled |

Internal validation:

| epoch | precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|---:|
| 2 | 0.97090 | 0.82468 | 0.87422 | 0.70402 |
| 6 | 0.96614 | 0.83377 | 0.86636 | 0.70690 |
| 10 | 0.95334 | 0.83117 | 0.86444 | 0.70116 |
| 14 | 0.95805 | 0.81818 | 0.85709 | 0.69888 |

## ROI Threshold Sweep

Enhanced ROI val, `imgsz=960`, match IoU `0.5`.

| checkpoint | conf | precision | recall | FP | FN | neg images with FP |
|---|---:|---:|---:|---:|---:|---:|
| lowlight `best.pt` | 0.05 | 0.814 | 0.838 | 59 | 50 | 3 |
| lowlight `best.pt` | 0.10 | 0.866 | 0.838 | 40 | 50 | 3 |
| lowlight `best.pt` | 0.25 | 0.930 | 0.818 | 19 | 56 | 3 |
| lowlight `best.pt` | 0.50 | 0.961 | 0.799 | 10 | 62 | 0 |
| lowlight `last.pt` | 0.05 | 0.817 | 0.825 | 57 | 54 | 3 |
| lowlight `last.pt` | 0.10 | 0.852 | 0.821 | 44 | 55 | 3 |
| lowlight `last.pt` | 0.25 | 0.916 | 0.812 | 23 | 58 | 3 |
| lowlight `last.pt` | 0.50 | 0.943 | 0.799 | 15 | 62 | 1 |
| lowlight `epoch10.pt` | 0.05 | 0.832 | 0.834 | 52 | 51 | 3 |
| lowlight `epoch10.pt` | 0.10 | 0.861 | 0.828 | 41 | 53 | 3 |
| lowlight `epoch10.pt` | 0.25 | 0.909 | 0.815 | 25 | 57 | 3 |
| lowlight `epoch10.pt` | 0.50 | 0.953 | 0.799 | 12 | 62 | 0 |

ROI readout:

- Domain-matched lowlight training recovered most of the test-time-only recall
  loss (`0.786` to `0.838` at `conf=0.05`).
- It did not beat the original-domain recall-oriented ROI checkpoint
  (`0.838` vs `0.854` at `conf=0.05`; `0.818` vs `0.834` at `conf=0.25`).
- It did improve precision and FP count compared with the original checkpoint
  at similar thresholds. For example, at `conf=0.10`, recall dropped from
  `0.847` to `0.838`, while precision rose from `0.845` to `0.866` and FP fell
  from `48` to `40`.

## Conclusion

The low-level processing idea is directionally reasonable only when the same
preprocessing is applied at train time and runtime. This experiment confirms
that test-time-only enhancement is harmful.

For the current CLAHE plus gamma transform:

- full-frame recall does not improve and small-object recall gets worse;
- ROI training recovers most of the preprocessing mismatch, but recall still
  stays slightly below the existing original-domain ROI checkpoint;
- ROI lowlight may be useful only as a precision/false-positive tradeoff, not
  as a recall improvement.

Do not promote either lowlight model for a recall-driven runtime. If dark-domain
matching is still worth pursuing, the next version should use a gentler
transform or collect real low-light/fixed-exposure positives rather than relying
on deterministic enhancement alone.

## Artifacts

| artifact | path |
|---|---|
| full-frame lowlight run | `tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_imgsz960_batch32_20260709` |
| full-frame baseline eval | `tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709/non_p2_fullframe_baseline_imgsz1536_20260709.md` |
| full-frame lowlight best eval | `tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709/non_p2_fullframe_lowlight_train_best_imgsz1536_20260709.md` |
| full-frame lowlight last eval | `tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709/non_p2_fullframe_lowlight_train_last_imgsz1536_20260709.md` |
| full-frame lowlight epoch6 eval | `tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709/non_p2_fullframe_lowlight_train_epoch6_imgsz1536_20260709.md` |
| ROI enhanced dataset | `tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_20260709` |
| ROI enhanced baseline sweep | `tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_20260709/baseline_epoch20_threshold_sweep_iou50.md` |
| ROI stable lowlight run | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_imgsz960_batch40_lr2e4_noamp_20260709` |
| ROI stable threshold sweep | `tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_imgsz960_batch40_lr2e4_noamp_20260709/threshold_sweep_iou50.md` |
