# TennisBot Current Status

Date: 2026-07-01

## Current Step

The project is at local operator validation. The main tracked paths are now:

- `tools/calibration` for the fixed DFOptix ChArUco OpenCV capture GUI;
- `tools/yolo` for annotation, model package operations, and pure YOLO detect
  GUI;
- `tools/stereo` for local 4K stereo YOLO coordinate display;
- `packages/core` and `packages/contracts` for runtime algorithms and shared
  contracts;
- `apps/live3d` for browser camera, YOLO, and 3D display.

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
with shutter/gain controls before calibration or Live3D runs.

## Important Gaps

The latest imported calibration package is not final physical acceptance. It has
`epipolar_rms_px=4.330`, above the `2.000` runtime review threshold. Fresh
calibration is still needed after the cameras are fixed in their real positions.

`tools/calibration` now mainlines the capture GUI, ChArUco mono solve, ChArUco
stereo solve, and runtime calibration package export. Fresh real calibration
still requires visible physical target captures after the cameras are fixed.

Live3D loads stereo calibration artifacts, but it does not know the camera rig's
pose relative to the tennis court. Current 3D output is camera-frame geometry,
not court coordinates.

Local Live3D operation relies on the browser readiness gates and visual runtime
state.

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
bun scripts/stereo.ts gui --tile
```

Dry-run the local stereo GUI defaults:

```bash
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
