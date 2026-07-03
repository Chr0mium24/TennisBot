# Local Runtime Operator Runbook

Date: 2026-07-03

## Scope

This runbook is the local-machine sequence for the current local reference
tools. The target real runtime is the headless ROS vision path documented in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md).

1. `tools/calibration` OpenCV GUI for fixed DFOptix ChArUco mono/stereo capture.
2. `tools/yolo` for pure YOLO detection and runtime model packages.
3. `tools/stereo` for local OpenCV 4K stereo YOLO coordinate display.
4. Live3D as a temporary/reference browser visualization path for two USB
   camera streams, ONNX YOLO inference, stereo 3D point, and trajectory
   prediction.

The board-side runtime and the future headless ROS vision node are not part of
this local reference flow yet.

## Start Surfaces

From the repository root:

```bash
bun scripts/live3d.ts
```

The launcher builds and starts the browser surface when it is not already
serving:

```text
Live3D:          http://127.0.0.1:5178/
```

For a quick status check without starting anything:

```bash
bun scripts/live3d.ts --status
```

Start the local stereo coordinate GUI:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui --tile
```

Observed result on 2026-06-29:

```text
ready  Live3D           http://127.0.0.1:5178/
```

## Calibration Order

Before taking calibration frames, check camera brightness/order:

```bash
bun scripts/calib.ts brightness
```

Open the live camera preview if exposure or UVC brightness needs tuning:

```bash
bun scripts/calib.ts preview
```

Use the mainline OpenCV GUI in order:

1. Confirm the fixed physical DFOptix ChArUco board is clean, flat, and matches
   the configured `15 mm` square / `11.25 mm` marker dimensions.
2. Tune camera shutter/brightness in `bun scripts/calib.ts preview` if the
   view is too dark, saturated, or noisy.
3. `bun scripts/calib.ts mono cam1` for the left mono capture and solve.
4. `bun scripts/calib.ts mono cam2` for the right mono capture and solve.
5. `bun scripts/calib.ts stereo` for stereo capture, solve, and runtime package
   export under `artifacts/calibration/stereo_cam1_cam2`.

## Live3D Order

Open `http://127.0.0.1:5178/` after the stereo package verifies:

1. Start cameras and confirm the Stereo cameras readiness gate is ready.
2. Start YOLO backend and put a tennis ball clearly inside both camera views.
3. Watch the readiness gates progress through left/right detection, stereo 3D
   point, and prediction curve.
4. Treat `prediction-ready` in the browser readiness gates as the local runtime
   target for a visible ball pass.

## Local Stereo GUI Order

After the stereo package verifies:

1. Run `bun scripts/stereo.ts gui --dry-run` to confirm default devices,
   artifact paths, and 4K capture settings.
2. Run `bun scripts/stereo.ts record` when raw left/right stereo video is
   needed. It writes under `runs/raw-stereo` and stops on `q` or `esc`; use
   `--duration <seconds>` only for an automatic stop.
3. Run `bun scripts/stereo.ts gui --tile` for YOLO detection on small 4K balls.
4. Add `--record-run` for long trajectory point/detection recording under
   `runs/stereo`.
5. Use `--detector hsv` only as a camera/geometry debugging fallback.
6. Read the right panel as left-camera-frame coordinates: x right, y down,
   z forward.

Open the replay frontend:

```bash
bun scripts/stereo.ts replay
```

The replay page lists recorded sessions and uses two UI range sliders for the
selected trajectory window. Do not pass replay time windows through CLI flags.

## Current Runtime Evidence

Historical hardware-verifier reports remain under `docs/archive/`, but the
current operator flow no longer requires a standalone acceptance report.
