# Legacy Calibration GUI Replacement Plan

Date: 2026-07-01

## Goal

Replace the current simplified mainline calibration capture GUI with the legacy CameraCalibLab ChArUco auto GUI behavior, while keeping the current `tools/calibration` solve/export commands usable from `scripts/calib.ts`.

## Plan

1. Replace the simplified `tools/calibration/src/camera_calib_lab/capture_gui.py` implementation with the old mono/stereo auto-capture behavior: full-corner gate, exposure check, stability window, position buckets, dwell capture, clickable Calibrate button, and legacy session artifacts.
2. Split the migrated implementation by responsibility: config/camera primitives, ChArUco detection, quality gates, OpenCV overlay rendering, artifact writing, and GUI loops.
3. Make `session.json` with `frames/frame_paths/topology` the only capture session format consumed by solver session loading; do not keep the simplified manifest parser.
4. Keep capture IDs (`left`/`right`) separate from runtime export IDs (`cam1`/`cam2`) in the stereo solver.
5. Update README/docs to state that the mainline GUI now uses the legacy CameraCalibLab auto-capture behavior.
6. Run the calibration tests with `uv` and commit all resulting changes.

## Constraints

- Do not add fake non-ROS WebSim catch-loop logic.
- Keep Python commands under `uv`.
- Preserve unrelated in-progress work where possible.
