# Camera / Vision Operator Runbook

Date: 2026-07-19

1. Run `uv run scripts/camera.py list` and confirm cam1 is left and cam2 is
   right.
2. Apply/check the intended profile with `camera.py controls`, then run
   `camera.py check` and raw `preview` as needed.
3. Calibrate cam1 and cam2 with `calib.py online mono`, then stereo with
   `calib.py online stereo`. Use `offline` only for an existing session.
4. Capture formal raw data with `record.py`; headless is the normal SSH path
   and `--gui` is the local operator path.
5. Validate YOLO independently with `test.py yolo mono/stereo` before testing
   `test.py triangulation stereo`.
6. Add `--record` only when the diagnostic frames/results must be retained.
   Use `--record-overlay` only when rendered review video is also required.
7. Source ROS and the control workspace, then use
   `test.py communication chassis-position` before starting vision runtime.
8. Start the ROS runtime only after camera, calibration, model, and pose input
   checks pass.

The test commands are diagnostics. They do not replace the real ROS/chassis chassis
pose/control chain and cannot validate a real catch loop without that backend.
