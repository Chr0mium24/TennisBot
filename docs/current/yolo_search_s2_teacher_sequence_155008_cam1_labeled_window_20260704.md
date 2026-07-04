# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.
It decides whether each frame runs full-frame search or ROI-only inference.
It does not use ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Settings

- Search model: `tools/yolo/workspace/runs/training/search_s2_teacher_yolov8n_p2_fullframe_imgsz640_20260704/weights/best.pt`
- ROI model: `tools/yolo/workspace/runs/training/search_s2_teacher_yolov8n_p2_fullframe_imgsz640_20260704/weights/best.pt`
- Sequence glob: `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam1_frame_*.jpg`
- Search imgsz: `640`
- ROI: `960x540` at imgsz `320`
- Expanded ROI: `1280x720`
- Lost after misses: `3`
- Expand after misses: `1`
- Edge margin ratio: `0.2`
- Distance score weight: `0.35`
- Max update distance ratio: `0.5`
- Candidate confirmation frames: `2`
- Acquire confirmation frames: `1`
- Candidate match distance ratio: `0.2`
- Same-frame search-on-miss imgsz: `0`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `cpu`
- CUDA available: `False`
- Torch: `2.12.1+cu130`

## Mode Counts

- Search frames: `96`
- ROI frames: `28`
- Expanded ROI frames: `16`
- Same-frame search-on-miss frames: `0`
- Lock acquisitions: `6`
- Lost events: `5`
- Detection updates used by tracker: `15`

## Result

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stateful_roi | 960x540->1280x720 | 640/320 | 124 | 49 | 9 | 10 | 40 | 0.184 | 0.474 | 36.85 | 37.43 | 13.57 | search=96 roi=28 expanded=16 acquired=6 lost=5 |

## Readout

- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.
- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.
- If the tracker locks onto false positives, precision and recall will expose that in this replay.
- Full ROS/Gazebo catch-loop validation is still separate and must use the real backend pose/control chain.
