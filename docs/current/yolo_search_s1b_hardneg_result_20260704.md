# YOLO Search-S1b Hard-Negative Result - 2026-07-04

## Goal

Test whether adding confirmed empty full-frame hard negatives improves the
Search-S1 full-frame acquisition model.

This is an offline detector and ROI replay experiment. It does not validate
real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Dataset

Dataset:

- `tools/yolo/workspace/runs/search_fullframe_s1b_hardneg_20260704`

Split:

| split | images | boxes | positive files | empty files |
|---|---:|---:|---:|---:|
| train | 332 | 157 | 157 | 175 |
| val | 104 | 52 | 52 | 52 |

Delta from Search-S1:

- Added 125 confirmed empty `20260701_154019_cam1` frames to train.
- Kept the Search-S1 val split unchanged for direct metric comparison.
- Kept `20260701_155008_cam1/cam2` excluded for final continuous replay.

No non-held-out cam2 positive images were available, so this experiment does not
solve the cam2 domain gap.

## Training

Initial model:

- `artifacts/models/tennis_ball_yolo/model.pt`

Output:

- `tools/yolo/workspace/runs/training/search_s1b_yolo26n_fullframe_hardneg_imgsz512_20260704/weights/best.pt`

Training stopped early at epoch 16. Best mAP50 and mAP50-95 were at epoch 4.

| metric | best epoch | best value |
|---|---:|---:|
| precision(B) | 1 | 0.50297 |
| recall(B) | 16 | 0.44231 |
| mAP50(B) | 4 | 0.27437 |
| mAP50-95(B) | 4 | 0.11226 |

Comparison on the unchanged validation split:

| model | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| Search-S1 best | 0.574 | 0.442 | 0.373 | 0.173 |
| Search-S1b best | 0.450 | 0.330 | 0.277 | 0.115 |

## Continuous Replay

Replay settings:

- Search imgsz: `512`
- ROI imgsz: `320`
- ROI window: `960x540`
- Expanded ROI: `1280x720`
- Device: CPU, 10 torch threads
- Held-out sequence: `20260701_155008_cam1/cam2`

Detailed reports:

- `docs/current/yolo_search_s1b_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_search_s1b_sequence_155008_cam2_labeled_window_20260704.md`
- `docs/current/yolo_search_s1b_roi_crop_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_search_s1b_roi_crop_sequence_155008_cam2_labeled_window_20260704.md`

| runtime config | cam | recall | precision | median ms/img | search frames | ROI frames |
|---|---|---:|---:|---:|---:|---:|
| Search-S1b search+ROI | cam1 | 0.347 | 0.680 | 17.23 | 94 | 30 |
| Search-S1b search+ROI | cam2 | 0.477 | 0.600 | 17.30 | 101 | 33 |
| Search-S1b search + ROI crop model | cam1 | 0.347 | 0.773 | 17.54 | 94 | 30 |
| Search-S1b search + ROI crop model | cam2 | 0.500 | 0.733 | 17.57 | 101 | 33 |

Estimated actual stereo budget using cam1+cam2 median times:

| runtime config | cam1+cam2 median ms | estimated stereo FPS |
|---|---:|---:|
| Search-S1b search+ROI | 34.53 | 28.96 |
| Search-S1b search + ROI crop model | 35.11 | 28.48 |

## Readout

Search-S1b should not be promoted.

What improved:

- Precision improved on held-out replay.
- False positives dropped in the two-model replay:
  - cam1 FP: `13 -> 5` compared with Search-S1 + ROI crop
  - cam2 FP: `47 -> 8` compared with Search-S1 + ROI crop

What failed:

- Recall is still far below the promotion target.
- Search frames increased, meaning the tracker spends more time unlocked:
  - cam1 search frames: `73 -> 94`
  - cam2 search frames: `41 -> 101`
- The hard-negative-only change suppresses detections but does not teach the
  model to acquire more true balls.

## Decision

Stop this branch as a promotion candidate. Do not continue adding empty frames
without adding positive acquisition data or teacher labels.

Next useful step:

1. Recover or add non-held-out cam2 positive images.
2. Mine teacher pseudo-labels from a stronger P2/high-resolution search teacher
   on unlabeled 0260701 sequences.
3. Train Search-S2 teacher or Search-S1c with added positive pseudo-labels, then
   keep `20260701_155008` as final replay.

