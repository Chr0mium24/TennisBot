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

The app currently runs in fixture mode with a Wave 9 YOLO inference adapter
boundary. Fixture mode builds contract-shaped sample detections and an in-memory
stereo calibration, then runs them through `packages/core` stereo pairing,
triangulation, and trajectory prediction before rendering the result.

The UI can open browser camera streams, validate YOLO/calibration artifact
metadata, and run an injected `YoloInferenceBackend` against the current left and
right video elements. The default backend is intentionally blocked because this
wave does not implement ONNX Runtime Web preprocessing, inference, or
postprocessing.

Fixture overlays remain explicitly labelled fixture-only. Runtime overlays are
rendered only when the injected backend returns valid detections.

This still does not run real YOLO inference by default, validate real tracking,
perform live stereo triangulation from runtime detections, or validate real
prediction.

## Config placeholders

The initial placeholders live in `src/config.ts`:

```text
left camera device: /dev/video0
right camera device: /dev/video2
YOLO model package: ../../artifacts/models/tennis_ball_yolo
stereo calibration package: ../../artifacts/calibration/stereo_cam1_cam2
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
```

`bun run dev` builds the static bundle and serves `dist/` on port `5178`.
