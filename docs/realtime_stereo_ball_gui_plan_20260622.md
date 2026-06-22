# Realtime Stereo Ball GUI Plan - 2026-06-22

## Goal

Build a local GUI that opens two USB cameras, uses the current tennis-ball YOLO detector, loads the current mono and stereo calibration parameters, and renders the ball position relative to the left camera in real time.

## Inputs

- Detector model: `TennisBallDetectorLab/yolo/models/yolo/best.pt`
- Left mono calibration: `CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7/calibration.json`
- Right mono calibration: `CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_cam2/calibration.json`
- Stereo extrinsics: `CameraCalibLab/runs/calibrations/dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622/calibration.json`
- Default camera devices: `/dev/video0` and `/dev/video1`

## Design

1. Add a `tbl stereo-gui` command under `TennisBallDetectorLab` so the GUI can reuse the existing YOLO runtime dependency.
2. Load CameraCalibLab mono calibration JSON files for intrinsics and the stereo JSON for rotation/translation.
3. Scale camera matrices when the live frame size differs from the calibration image size.
4. Run YOLO on left and right frames, optionally using tiled inference for 4K frames where the ball is small.
5. Convert detection centers to rectified coordinates with `cv2.undistortPoints`.
6. Match left/right detections by epipolar error, positive disparity, confidence, and temporal continuity.
7. Triangulate the selected match with `cv2.triangulatePoints`.
8. Render side-by-side camera views and a metric X/Z position panel in an OpenCV window.

## Runtime Notes

- Coordinates follow OpenCV camera convention: `x` right, `y` down, `z` forward from the left camera.
- The command does not solve synchronization. It reads both devices sequentially, which is suitable for a live visualization but not a hardware-triggered measurement chain.
- The user can override all calibration paths, model path, camera devices, confidence threshold, and inference image size.
