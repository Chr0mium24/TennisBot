# Local Runtime Operator Runbook

Date: 2026-06-29

## Scope

This runbook is the local-machine sequence for the current TennisBot runtime:

1. `tools/calibration` OpenCV GUI for fixed DFOptix ChArUco mono/stereo capture.
2. `tools/yolo` for pure YOLO detection and runtime model packages.
3. Live3D for two USB camera streams, ONNX YOLO inference, stereo 3D point,
   trajectory prediction, and hardware verification.

The board-side runtime is not part of this flow.

## Start Surfaces

From the repository root:

```bash
bun scripts/start-local-runtime.ts
```

The launcher builds and starts the browser surface when it is not already
serving:

```text
Live3D:          http://127.0.0.1:5178/
```

For a quick status check without starting anything:

```bash
bun scripts/start-local-runtime.ts --status
```

Observed result on 2026-06-29:

```text
ready  Live3D           http://127.0.0.1:5178/
```

Normal startup also prints the current physical validation next action.

## Calibration Order

Before taking calibration frames, run the preflight:

```bash
mkdir -p docs/archive/YYYYMMDD/probes
bun scripts/operator-preflight.ts --output docs/archive/YYYYMMDD/probes/local_runtime_preflight_YYYYMMDD.md
```

Observed result on 2026-06-29:

```text
passed Live3D surface
passed YOLO package
passed Stereo calibration package
passed USB camera devices
```

Use the mainline OpenCV GUI in order:

1. Confirm the fixed physical DFOptix ChArUco board is clean, flat, and matches
   the configured `15 mm` square / `11.25 mm` marker dimensions.
2. `cd tools/calibration && uv run camera-calib-lab capture charuco-auto-gui ...`
   for each mono camera capture.
3. `cd tools/calibration && uv run camera-calib-lab capture stereo-charuco-auto-gui ...`
   for stereo capture.
4. `cd tools/calibration && uv run camera-calib-lab solve mono ...` for each
   mono capture.
5. `cd tools/calibration && uv run camera-calib-lab solve stereo ...` to export
   the runtime calibration package under `artifacts/calibration/stereo_cam1_cam2`.

## Live3D Order

Open `http://127.0.0.1:5178/` after the stereo package verifies:

1. Start cameras and confirm the Stereo cameras readiness gate is ready.
2. Start YOLO backend and put a tennis ball clearly inside both camera views.
3. Watch the readiness gates progress through left/right detection, stereo 3D
   point, and prediction curve.
4. Run the hardware verifier for durable evidence:

```bash
cd apps/live3d
mkdir -p ../../docs/archive/YYYYMMDD/live3d
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/archive/YYYYMMDD/live3d/live3d_hardware_loop_ball_YYYYMMDD.md
```

The hardware run is complete only when it reaches `prediction-ready`.

## Current Hardware Evidence

The latest saved probe is
[`live3d_hardware_readiness_gates_20260629.md`](../archive/20260629/live3d/live3d_hardware_readiness_gates_20260629.md).
It proves the app server, runtime snapshot, YOLO artifact, calibration artifact,
two USB camera streams, and non-black browser frames are working. It is still
blocked at left/right YOLO detection because no tennis ball is visible in the
current scene.

The latest preflight report is
[`local_runtime_preflight_20260629.md`](../archive/20260629/probes/local_runtime_preflight_20260629.md).
It verifies the Live3D browser surface, the YOLO package, the stereo calibration
package, and `/dev/video0` plus `/dev/video2`.
