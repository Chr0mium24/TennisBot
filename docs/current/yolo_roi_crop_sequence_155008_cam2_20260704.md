# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.
It decides whether each frame runs full-frame search or ROI-only inference.
It does not use real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Model: `tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`
- Sequence glob: `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam2_frame_*.jpg`
- Search imgsz: `416`
- ROI: `960x540` at imgsz `320`
- Expanded ROI: `1280x720`
- Lost after misses: `3`
- Expand after misses: `1`
- Edge margin ratio: `0.2`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `cpu`
- CUDA available: `False`
- Torch: `2.12.1+cu130`

## Mode Counts

- Search frames: `351`
- ROI frames: `87`
- Expanded ROI frames: `33`
- Lock acquisitions: `15`
- Lost events: `15`
- Detection updates used by tracker: `57`

## Result

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stateful_roi | 960x540->1280x720 | 416/320 | 438 | 44 | 17 | 45 | 27 | 0.386 | 0.274 | 14.46 | 22.48 | 34.59 | search=351 roi=87 expanded=33 acquired=15 lost=15 |

## Readout

- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.
- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.
- If the tracker locks onto false positives, precision and recall will expose that in this replay.
- Full real ROS/chassis catch-loop validation is still separate and must use the real backend pose/control chain.
