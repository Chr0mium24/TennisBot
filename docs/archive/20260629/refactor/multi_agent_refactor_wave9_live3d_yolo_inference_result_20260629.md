# Multi-Agent Refactor Wave 9 Live3D YOLO Inference Result

Date: 2026-06-29

Branch: `refactor/live3d-yolo-inference`

## Summary

Wave 9 added the Live3D-side YOLO inference data path as an app-local TypeScript
adapter boundary. The app now has an injectable `YoloInferenceBackend`, left and
right detection runtime state, backend-output conversion into the shared
`YoloDetection2D` contract, and UI wiring that can render runtime detection
overlays when a backend returns valid detections.

Fixture overlays remain available and are still labelled fixture-only. The
default backend is intentionally blocked and does not claim real YOLO inference.

## What Is Real

- `apps/live3d/src/detections.ts` defines the runtime backend interface,
  detection status types, conversion helpers, and overlay box conversion.
- Backend boxes are validated, clamped to the frame, and converted into
  contract-shaped `YoloDetection2D` records with stable IDs, camera IDs, frame
  IDs, timestamps, confidence, bounding boxes, and center pixels.
- Live3D UI has Start/Stop YOLO adapter controls gated by ready cameras and a
  loaded YOLO artifact metadata package.
- Left and right YOLO runtime statuses render independently.
- Runtime detections take precedence over fixture overlays only when valid
  backend detections are available.
- Tests use fake and blocked backends only; they require no USB cameras, model
  files, browser permissions, or `onnxruntime-web`.
- Lead review tightened the adapter by rejecting non-`tennis_ball` classes,
  treating empty backend output as a valid zero-detection frame, escaping
  backend-provided overlay labels, refreshing Stop YOLO immediately, and
  preventing stopped async inference runs from writing stale UI state.

## Adapter-Only Items

- The default app backend returns a blocked status explaining that Wave 9 only
  wires the injectable adapter path.
- Runtime inference is one-shot from the current video elements when the user
  starts the adapter. Continuous frame scheduling is left for the real backend
  wave.

## Remaining Work

- Implement the real browser ONNX Runtime Web backend for exported
  `model.onnx` packages, including preprocessing and postprocessing.
- Feed real left/right detections through stereo pairing, triangulation, and
  trajectory prediction.
- Validate the full real-machine closed loop with ROS/Gazebo backend pose and
  control chain before claiming real catch-loop completion.

## Validation

Passed:

```bash
cd apps/live3d && bun test
cd apps/live3d && bun run typecheck
cd apps/live3d && bun run build
git diff --check
```

Lead review result after the runtime-state fixes: 23 passing tests, 0 failures.
