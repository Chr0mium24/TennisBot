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
scraping UI text. The same runtime snapshot now carries readiness gates for
YOLO artifact, calibration artifact, stereo cameras, left/right detections,
stereo 3D point, and prediction. The status panel renders those gates directly
so the operator can see whether the next missing input is software, cameras,
the visible ball, triangulation, or prediction.

This implements the browser software path. Hardware smoke has opened two real
USB cameras in Chrome and run the exported ONNX model on browser frames. The
current default camera request is `1280x720@30`, matching the local UVC
devices' supported mode. Direct V4L2 tests showed `1280x720` MJPG streams work,
while high-resolution YUYV streams time out. With `--prepare-uvc-controls`, the
hardware verifier can set high-brightness UVC controls and capture non-black
browser frames. The latest boosted report still has zero YOLO detections
because the captured scene is uniform gray and contains no visible tennis ball.

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
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/live3d_hardware_loop_YYYYMMDD.md
```

`bun run dev` builds the static bundle and serves `dist/` on port `5178`.
`bun run verify:hardware` builds or reuses the local app server, launches
Chrome with camera permission auto-approved, starts both USB cameras, starts
YOLO, polls the runtime snapshot, captures left/right video PNG frames with
brightness statistics, and writes a Markdown report. A passing run requires the
runtime status to reach `prediction-ready`; no-ball or near-black scenes are
reported as failed hardware validation, not as software success.
The report includes a fixed acceptance checklist covering app server, snapshot,
YOLO artifact, calibration artifact, stereo cameras, frame quality, left/right
detections, stereo triangulation, and trajectory prediction. It also prints the
runtime readiness gates published by `window.__tennisbotLive3dSnapshot`, matching
the browser status panel. When the runtime is ready but the scene has no visible
tennis ball, the detection gates are marked `blocked` with the next physical
action instead of being conflated with a software failure.
`--prepare-uvc-controls` applies the local USU Camera 4K controls that recovered
non-black frames during validation: brightness `64`, gain `255`, manual
exposure `2047` on `/dev/video0` and `/dev/video2`.
