# TennisBot Live3D

`apps/live3d` is the first shell for the real-machine stereo runtime UI. It is a
TypeScript and Bun frontend app that defines the intended product surface:

- two USB camera panels for left and right feeds;
- 2D YOLO detection overlays on each camera image;
- a 3D scene area for ball point, trail, predicted curve, and landing point;
- a status panel for camera, model, calibration, tracking, and prediction
  readiness;
- config placeholders for camera devices and artifact package paths.

## Current mode

The app currently runs with a fixture fallback and a Wave 11 runtime 3D path.
Fixture mode builds contract-shaped sample detections and an in-memory stereo
calibration, then runs them through `packages/core` stereo pairing,
triangulation, and trajectory prediction before rendering the fallback result.

The UI can open browser camera streams, validate YOLO/calibration artifact
metadata, and run a `YoloInferenceBackend` loop against the current left and
right video elements. When the YOLO artifact package is loaded and its selected
model is ONNX-compatible, the default backend uses `onnxruntime-web` to load the
model, preprocess readable frames, run `session.run`, and postprocess
tennis-ball detections. The backend serializes ONNX session runs so left/right
camera inference does not call the same WASM session concurrently. If the
artifact package is missing or blocked, the backend remains explicitly blocked.

Fixture overlays and the fixture 3D scene remain explicitly labelled
fixture-only. Runtime overlays are rendered only when the ONNX or injected
backend returns valid detections. When both runtime YOLO sides produce detections
and the stereo calibration package is loaded, the app selects a stereo pair,
triangulates a runtime 3D ball point, maintains a runtime trail, and renders a
runtime prediction/landing once at least two runtime points are available.
The page also exposes `window.__tennisbotLive3dSnapshot` so automated hardware
checks can read camera, artifact, detection, and runtime 3D state without
scraping UI text.

This implements the browser software path. Hardware smoke has opened two real
USB cameras in Chrome and run the exported ONNX model on live frames. The
current scene did not contain a detectable tennis ball, so runtime ball
detections, 3D point stability, and prediction updates still need a ball-in-view
validation pass.

## Config placeholders

The initial placeholders live in `src/config.ts`:

```text
left camera device: /dev/video0
right camera device: /dev/video2
YOLO model package: /artifacts/models/tennis_ball_yolo
stereo calibration package: /artifacts/calibration/stereo_cam1_cam2
```

These paths match the target artifact boundaries from the architecture
simplification plan. The live runtime should consume exported artifact packages
only, not training datasets or calibration capture sessions.

## Commands

```bash
bun install
bun run dev
bun run typecheck
bun test
bun run build
bun run verify:hardware -- --timeout-ms 30000 --output ../../docs/live3d_hardware_loop_YYYYMMDD.md
```

`bun run dev` builds the static bundle and serves `dist/` on port `5178`.
`bun run verify:hardware` builds or reuses the local app server, launches
Chrome with camera permission auto-approved, starts both USB cameras, starts
YOLO, polls the runtime snapshot, and writes a Markdown report. A passing run
requires the runtime status to reach `prediction-ready`; no-ball scenes are
reported as failed hardware validation, not as software success.
