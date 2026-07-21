# Camera Refactor Phase 5/6 Test and Retirement Result

Date: 2026-07-19

## Implemented

- Moved runtime calibration loading, YOLO/ROI inference, stereo matching,
  triangulation, and rendering into the shared `tennisbot-vision` package.
- Added `scripts/test.py` for mono/stereo YOLO, stereo triangulation, and the
  existing read-only chassis-position ROS check.
- GUI and headless tests use the same frame loop and algorithms. Headless mode
  prints per-frame fields and `--json` emits machine-readable one-line JSON.
- Added `--record`, `--record-overlay`, `--record-root`, and
  `--record-session` only to online test commands.
- The shared recording sink receives already-captured frame objects and never
  opens V4L2. It writes raw mono/stereo video, frame/pair logs, detections,
  triangulation, and optional overlay video.
- ROS runtime now imports the installed `tennisbot_vision` package directly;
  the source-path parameter and `sys.path` mutation were removed.
- Removed `scripts/stereo.py`, `scripts/recording.py`,
  `scripts/camera_controls.py`, `scripts/check-chassis-position.py`, and the
  obsolete `tools/stereo` package/replay frontend.
- The recording package public parser no longer exposes extraction,
  normalization, or config-inspection commands. Their implementation is
  retained internally pending a separate media/data utility decision.
- Updated active architecture, status, command, device, runbook, runtime, and
  root documentation.

## Non-hardware verification

```text
packages/vision-python: 7 passed
tools/recording: 10 passed
tools/calibration: 26 passed
src/tennisbot_vision_runtime: 5 passed
python compileall: passed
```

CLI dry runs passed for:

- mono/stereo YOLO;
- stereo triangulation;
- raw and overlay test recording flags;
- mono/stereo GUI/headless recorder mapping;
- online/offline calibration construction;
- communication help routing.

Repository searches confirm the active Python code contains no
`tennisbot_stereo`, `tools/stereo`, or `stereo_tool_python_path` reference.

## Physical validation still required

No `/dev/video*` cameras or sourced real ROS/chassis control backend were available.
Consequently this result does not claim camera encoder/GUI performance,
physical calibration quality, communication success, or real catch-loop
validation.
