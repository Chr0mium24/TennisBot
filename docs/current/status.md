# TennisBot Current Status

Date: 2026-07-03

## Current Step

The project is moving from local operator visualization toward a headless ROS
vision runtime. The main tracked paths are now:

- `tools/calibration` for the fixed DFOptix ChArUco OpenCV capture GUI;
- `tools/yolo` for annotation, model package operations, and pure YOLO detect
  GUI;
- `tools/stereo` for local 4K stereo YOLO coordinate display;
- `packages/core` and `packages/contracts` for runtime algorithms and shared
  contracts;
- `src` for ROS2 interface packages and the TennisBot vision adapter;
- `apps/live3d` as a temporary/reference browser camera, YOLO, and 3D display
  path, not the target real runtime.

## Ready Now

The local launcher has reported the browser surface ready:

```text
ready  Live3D           http://127.0.0.1:5178/
```

The current quick camera-device tool is:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
bun scripts/calib.ts preview
```

It prints average brightness for two USB cameras and can open a live preview
with shutter and brightness controls before calibration or Live3D runs.

## Important Gaps

The current local stereo calibration package is accepted and has no runtime
quality warning:

```text
stereo_rms_reprojection_px=0.2121
epipolar_rms_px=0.2568
rectification_y_p95_px=0.4296
baseline_m=0.1650
```

`tools/calibration` now mainlines the capture GUI, ChArUco mono solve, ChArUco
stereo solve, and runtime calibration package export.

Live3D loads stereo calibration artifacts, but it does not know the camera rig's
pose relative to the tennis court. Current 3D output is camera-frame geometry,
not court coordinates.

The target real runtime is documented in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md). The main
remaining gaps are:

- add a headless ROS vision node;
- consume chassis pose with at least `x`, `y`, `yaw`, and `stamp`;
- configure fixed chassis-to-camera extrinsics;
- use ROS clock for image capture stamps and chassis pose timestamps;
- transform observations into field/interface coordinates before trajectory
  fitting;
- publish `/vision/target_prediction` and verify the adapter chain to
  `/target/raw` and `/target/managed`.

## Next Commands

Run pure YOLO camera detection:

```bash
cd tools/yolo
uv run --extra detect tennisbot-yolo detect-gui \
  --devices /dev/video0,/dev/video2 \
  --width 3840 \
  --height 2160 \
  --fourcc MJPG \
  --model ../../artifacts/models/tennis_ball_yolo/model.pt \
  --tile \
  --imgsz 1280 \
  --display-width 720
```

Run local stereo coordinate display:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts record --duration 60
bun scripts/stereo.ts gui --tile
bun scripts/stereo.ts gui --tile --record-run
bun scripts/stereo.ts replay
```

`record` stores raw left/right videos and timestamp metadata under
`runs/raw-stereo`. Without `--duration`, it continues until `q` or `esc` is
pressed in the preview window.

Dry-run the local stereo GUI defaults:

```bash
bun scripts/stereo.ts record --dry-run
bun scripts/stereo.ts gui --dry-run
```

Capture calibration frames:

```bash
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

Start or check Live3D:

```bash
bun scripts/live3d.ts
bun scripts/live3d.ts --status
```

Open Live3D and observe the browser readiness gates through camera startup,
left/right detections, stereo 3D point, and prediction curve.
