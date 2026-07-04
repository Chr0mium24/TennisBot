# YOLO ROI Continuous Sequence Replay - 2026-07-04

## Scope

This report tests a continuous labeled video capture from the YOLO annotation
set with the ROI crop model trained on 2026-07-04.

This remains an offline monocular detector replay:

- no ROS/Gazebo validation;
- no live camera capture;
- no stereo triangulation timing;
- no `/target/raw` catch-loop claim.

## Sequence

Selected capture:

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

The capture has both camera streams and labels:

| stream | images | non-empty GT frames | GT boxes | continuous label-file window |
|---|---:|---:|---:|---|
| cam1 | 428 | 49 | 49 | frames 1-124, frame 123 missing |
| cam2 | 438 | 44 | 44 | frames 1-134 |

The full image sequence is longer than the continuous label-file window. The
benchmark treats frames without labels as negative frames, so full-sequence
precision can be lower than the labeled-window precision if later frames are not
fully annotated.

## Model And Runtime Settings

Model:

`tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`

Runtime settings:

- search imgsz: `416`
- locked ROI: `960x540`
- ROI imgsz: `320`
- expanded ROI: `1280x720`
- confidence threshold: `0.05`
- match IoU: `0.5`
- CPU threads: `10`

## Results

Raw reports:

- `docs/current/yolo_roi_crop_sequence_155008_cam1_20260704.md`
- `docs/current/yolo_roi_crop_sequence_155008_cam2_20260704.md`
- `docs/current/yolo_roi_crop_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_roi_crop_sequence_155008_cam2_labeled_window_20260704.md`

### Full Sequence

| stream | images | GT | search frames | ROI frames | expanded ROI | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 428 | 49 | 115 | 313 | 194 | 18 | 126 | 31 | 0.367 | 0.125 | 9.90 | 50.51 |
| cam2 | 438 | 44 | 351 | 87 | 33 | 17 | 45 | 27 | 0.386 | 0.274 | 14.46 | 34.59 |

### Continuous Label Window Only

| stream | images | GT | search frames | ROI frames | expanded ROI | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 first 124 | 124 | 49 | 46 | 78 | 41 | 18 | 27 | 31 | 0.367 | 0.400 | 9.91 | 50.46 |
| cam2 first 134 | 134 | 44 | 103 | 31 | 11 | 17 | 9 | 27 | 0.386 | 0.654 | 22.28 | 22.44 |

## Readout

This sequence confirms the runtime split:

- cam1 can exceed `50 FPS` estimated stereo detector budget when it spends most
  frames in ROI mode;
- cam2 spends most frames in full-frame search and drops to `22-35 FPS`;
- recall remains low on both streams: `0.367` on cam1 and `0.386` on cam2.

The low recall is not just a precision-accounting artifact. Restricting to the
continuous label window improves precision, but recall stays the same because
the same GT boxes are missed.

## Recall 1.000 Audit

The earlier `recall=1.000` row was:

`oracle_roi | roi_960x540_320 | 60 images | 28 GT | TP=28 | FP=28 | FN=0`

That row is not a tracker/runtime result. It uses labels to place the crop around
the GT object before inference, so it is an upper-bound test for locked ROI
detector budget. Under that oracle condition, recall can legitimately be `1.000`
because all `28` GT boxes had at least one matching prediction.

It is misleading if read as actual runtime recall. The real stateful replay on
this continuous sequence is only `0.367-0.386` recall, so the runtime problem is
still search/lock stability and missed GT frames, not only raw ROI inference
speed.

## Decision

Do not use the oracle ROI recall as proof of the full system. It only proves that
the detector can see the ball when the ROI is already correctly placed.

The next useful engineering step is to wire stateful ROI into the real stereo
detector path and evaluate left/right pairing together. The model path can hit
the speed target in ROI mode, but the current lock/search behavior is not yet
reliable enough on this continuous capture.
