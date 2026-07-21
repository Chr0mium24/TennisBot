# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on an ordered real-frame sequence.
It decides whether each frame runs full-frame search or ROI-only inference.
It does not use real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## Settings

- Search model: `artifacts/models/tennis_ball_yolo/model.pt`
- ROI model: `artifacts/models/tennis_ball_yolo/model.pt`
- Sequence glob: `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam1_frame_*.jpg`
- Search imgsz: `512`
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

- Search frames: `59`
- ROI frames: `65`
- Expanded ROI frames: `22`
- Same-frame search-on-miss frames: `0`
- Lock acquisitions: `9`
- Lost events: `8`
- Detection updates used by tracker: `45`

## Result

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| stateful_roi | 960x540->1280x720 | 512/320 | 124 | 49 | 23 | 58 | 26 | 0.469 | 0.284 | 22.32 | 34.87 | 22.41 | search=59 roi=65 expanded=22 acquired=9 lost=8 |

## Readout

- This is closer to the intended runtime than `coarse_roi`, because locked frames do not also run full-frame search.
- The result still uses one monocular image sequence and estimates stereo FPS as sequential left+right processing.
- If the tracker locks onto false positives, precision and recall will expose that in this replay.
- Full real ROS/chassis catch-loop validation is still separate and must use the real backend pose/control chain.
