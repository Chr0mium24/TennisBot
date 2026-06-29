# YOLO Detect GUI Plan

Date: 2026-06-29

## Goal

Add a minimal mainline GUI for checking YOLO tennis-ball detections from USB
cameras without calibration, stereo triangulation, or trajectory prediction.

## Scope

- Add `tennisbot-yolo detect-gui` under `tools/yolo`.
- Open one to four V4L2/OpenCV camera devices.
- Run Ultralytics YOLO on full frames or tiled 4K crops.
- Draw detection boxes on a downscaled OpenCV preview.
- Keep detector dependencies optional behind the `detect` extra.

## Out Of Scope

- Calibration loading.
- Rectification.
- Stereo matching.
- 3D point calculation.
- Live3D browser integration.
