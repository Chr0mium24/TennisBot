# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.
It decides whether each frame runs full-frame search or ROI-only inference.
It does not use ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Settings

- Model: `tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`
- Sequence glob: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images/0260701/20260701_154019_cam1_frame_*.jpg`
- Search imgsz: `512`
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

- Search frames: `352`
- ROI frames: `100`
- Expanded ROI frames: `21`
- Lock acquisitions: `8`
- Lost events: `8`
- Detection updates used by tracker: `84`

## Result

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stateful_roi | 960x540->1280x720 | 512/320 | 452 | 52 | 37 | 65 | 15 | 0.712 | 0.363 | 16.15 | 16.87 | 30.96 | search=352 roi=100 expanded=21 acquired=8 lost=8 |

## Readout

- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.
- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.
- If the tracker locks onto false positives, precision and recall will expose that in this replay.
- Full ROS/Gazebo catch-loop validation is still separate and must use the real backend pose/control chain.
