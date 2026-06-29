# Local Runtime Operator Runbook

Date: 2026-06-29

## Scope

This runbook is the local-machine sequence for the current TennisBot runtime:

1. Calibration GUI for target generation, mono calibration, stereo calibration,
   and package verification.
2. Live3D for two USB camera streams, ONNX YOLO inference, stereo 3D point,
   trajectory prediction, and hardware verification.

The board-side runtime is not part of this flow.

## Start Surfaces

From the repository root:

```bash
bun scripts/start-local-runtime.ts
```

The launcher builds and starts the two browser surfaces when they are not
already serving:

```text
Live3D:          http://127.0.0.1:5178/
Calibration GUI: http://127.0.0.1:5188/
```

For a quick status check without starting anything:

```bash
bun scripts/start-local-runtime.ts --status
```

Observed result on 2026-06-29:

```text
ready  Live3D           http://127.0.0.1:5178/
ready  Calibration GUI  http://127.0.0.1:5188/
```

## Calibration Order

Before taking calibration frames, run the preflight:

```bash
bun scripts/operator-preflight.ts --output docs/local_runtime_preflight_YYYYMMDD.md
```

Observed result on 2026-06-29:

```text
passed Live3D surface
passed Calibration GUI surface
passed YOLO package
passed Stereo calibration package
passed USB camera devices
```

Open `http://127.0.0.1:5188/` and use the presets in order:

1. `Target`: run `target charuco`, print the generated SVG at 100% scale, and
   confirm one printed square measures 15 mm.
2. `Cam1 Mono`: capture, inspect, detect ChArUco, solve, then package verify.
3. `Cam2 Mono`: capture, inspect, detect ChArUco, solve, then package verify.
4. `Stereo`: capture, inspect, detect ChArUco, solve, then package verify.

Generated JSON artifacts are automatically imported into the GUI workspace when
commands run through the local command bridge.

## Live3D Order

Open `http://127.0.0.1:5178/` after the stereo package verifies:

1. Start cameras and confirm the Stereo cameras readiness gate is ready.
2. Start YOLO backend and put a tennis ball clearly inside both camera views.
3. Watch the readiness gates progress through left/right detection, stereo 3D
   point, and prediction curve.
4. Run the hardware verifier for durable evidence:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/live3d_hardware_loop_ball_YYYYMMDD.md
```

The hardware run is complete only when it reaches `prediction-ready`.

## Current Hardware Evidence

The latest saved probe is
[`live3d_hardware_readiness_gates_20260629.md`](live3d_hardware_readiness_gates_20260629.md).
It proves the app server, runtime snapshot, YOLO artifact, calibration artifact,
two USB camera streams, and non-black browser frames are working. It is still
blocked at left/right YOLO detection because no tennis ball is visible in the
current scene.

The latest preflight report is
[`local_runtime_preflight_20260629.md`](local_runtime_preflight_20260629.md).
It verifies both browser surfaces, the YOLO package, the stereo calibration
package, and `/dev/video0` plus `/dev/video2`.
