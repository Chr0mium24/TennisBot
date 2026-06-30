# TennisBot Current Status

Date: 2026-06-30

## Current Step

The project is at local operator validation. The main tracked paths are now:

- `tools/calibration` for the fixed DFOptix ChArUco OpenCV capture GUI;
- `tools/yolo` for annotation, model package operations, and pure YOLO detect
  GUI;
- `packages/core` and `packages/contracts` for runtime algorithms and shared
  contracts;
- `apps/live3d` for browser camera, YOLO, 3D display, and hardware verification.

## Ready Now

The local launcher has reported the browser surface ready:

```text
ready  Live3D           http://127.0.0.1:5178/
```

The current quick camera-device tool is:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
```

It prints average brightness for two USB cameras so a covered or dark camera can
be identified before calibration or Live3D runs.

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

Live3D hardware verification has not completed a real ball pass yet. A complete
run requires a visible tennis ball in both camera views and a final
`prediction-ready` runtime snapshot.

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

Capture calibration frames:

```bash
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

Start or check Live3D:

```bash
bun scripts/live3d.ts
bun scripts/live3d.ts --status
```

Run a hardware evidence pass:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/archive/20260629/live3d/live3d_hardware_loop_ball_YYYYMMDD.md
```

The system should not be treated as physically accepted until the hardware
report reaches `prediction-ready`.
