# YOLO Non-P2 Full-Frame and ROI Low-Light Plan - 2026-07-09

## Question

Stop the P2 direction and test whether the existing non-P2 detector path gets
better recall when train-time and test-time images use the same deterministic
low-light enhancement.

This is a detector-only experiment. It does not validate stereo triangulation,
trajectory prediction, real ROS/chassis, or chassis control.

## Hypothesis

The earlier P2 test showed that applying low-light enhancement only at test
time did not help. The still-plausible version is domain matching: train and
evaluate the model on the same enhanced image domain.

If recall improves, the preprocessing may be useful only if the same transform
is wired into runtime before YOLO inference. If recall drops or empty-frame
false positives rise, the enhancement is amplifying background texture more
than ball signal.

## Transform

Use the already selected deterministic transform:

1. CLAHE on the LAB `L` channel with clip limit `2.0` and tile grid `8x8`.
2. Gamma brightening with `gamma=0.75`.

Image dimensions and YOLO labels stay unchanged.

## Full-Frame Experiment

Base dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708`

Enhanced dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_20260709`

Enhanced benchmark:

`tools/yolo/workspace/runs/final_raw_benchmark_v1_lowlight_g075_clahe2_20260709`

Seed checkpoint:

`tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_imgsz960_batch32_20260708/weights/best.pt`

Training run:

`tools/yolo/workspace/runs/training/final_trainpool_tiny_fixed_cp_lowlight_g075_clahe2_imgsz960_batch32_20260709`

Evaluate at `imgsz=1536`, `conf=0.05,0.25`, match IoU `0.5`.

Compare against the original-domain full-frame benchmark:

| imgsz | conf | overall R/P | fixed R/P | small R/P | empty FP imgs | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|
| 1536 | 0.05 | 0.616 / 0.459 | 0.511 / 0.483 | 0.080 / 0.200 | 33 | 80.09 |
| 1536 | 0.25 | 0.592 / 0.500 | 0.502 / 0.533 | 0.071 / 0.200 | 29 | 80.09 |

## ROI Experiment

Base dataset:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_20260708`

Enhanced dataset to generate:

`tools/yolo/workspace/runs/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_20260709`

Seed checkpoint:

`tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_imgsz960_batch40_20260708/weights/epoch20.pt`

`epoch20.pt` is selected because the previous ROI result showed it was the best
recall-oriented checkpoint at `imgsz=960`.

Training run:

`tools/yolo/workspace/runs/training/fixed_exposure_roi1024x576_3000_lowlight_g075_clahe2_imgsz960_batch40_20260709`

Evaluate `best.pt`, `last.pt`, and saved epoch checkpoints on the enhanced ROI
validation split using match IoU `0.5` and thresholds `0.05,0.10,0.25,0.50`.

Compare against the original-domain ROI recall-oriented checkpoint:

| checkpoint | conf | precision | recall | FP | FN |
|---|---:|---:|---:|---:|---:|
| `epoch20.pt` | 0.05 | 0.760 | 0.854 | 83 | 45 |
| `epoch20.pt` | 0.10 | 0.845 | 0.847 | 48 | 47 |
| `epoch20.pt` | 0.25 | 0.908 | 0.834 | 26 | 51 |
| `epoch20.pt` | 0.50 | 0.958 | 0.815 | 11 | 57 |

## Run Order

1. Confirm no remote training is running.
2. Evaluate the current non-P2 full-frame checkpoint on the enhanced benchmark.
3. Continue-train the non-P2 full-frame checkpoint on the enhanced full-frame
   trainset.
4. Evaluate the continued full-frame checkpoints on the enhanced benchmark.
5. Generate the enhanced ROI train/val dataset.
6. Evaluate the current ROI `epoch20.pt` checkpoint on the enhanced ROI val set.
7. Continue-train the ROI checkpoint on the enhanced ROI trainset.
8. Sweep thresholds for ROI checkpoints on the enhanced ROI val set.
9. Record results in Markdown before considering any runtime change.

## Success Signal

The full-frame model is useful only if fixed and small recall improve at
`imgsz=1536` without a large increase in empty-frame false positives.

The ROI model is useful only if recall improves over the previous `epoch20.pt`
numbers while preserving acceptable precision at `conf=0.10-0.25`.

Neither model should be promoted unless the same preprocessing is added to the
runtime path and evaluated there.
