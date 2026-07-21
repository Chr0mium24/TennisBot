# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.
It decides whether each frame runs full-frame search or ROI-only inference.
It does not use real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Model: `tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`
- Sequence glob: `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam1_frame_*.jpg`
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

- Search frames: `46`
- ROI frames: `78`
- Expanded ROI frames: `41`
- Lock acquisitions: `20`
- Lost events: `19`
- Detection updates used by tracker: `39`

## Result

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stateful_roi | 960x540->1280x720 | 416/320 | 124 | 49 | 18 | 27 | 31 | 0.367 | 0.400 | 9.91 | 14.50 | 50.46 | search=46 roi=78 expanded=41 acquired=20 lost=19 |

## Readout

- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.
- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.
- If the tracker locks onto false positives, precision and recall will expose that in this replay.
- Full real ROS/chassis catch-loop validation is still separate and must use the real backend pose/control chain.
