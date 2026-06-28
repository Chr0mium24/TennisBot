# Multi-Agent Refactor Wave 10 Live3D ONNX Backend Result

Date: 2026-06-29

Branch: `refactor/live3d-onnx-backend`

## Summary

Wave 10 implemented the Live3D browser `onnxruntime-web` backend behind the
existing `YoloInferenceBackend` boundary. When the YOLO artifact package loads
and its selected model is ONNX-compatible, Live3D now creates an
`OnnxYoloInferenceBackend` by default instead of the Wave 9 blocked adapter.

The backend resolves the selected ONNX model URL from the loaded artifact
package path and metadata, lazily creates a browser ORT session, preprocesses a
readable frame into RGB/BGR NCHW float tensor data with letterbox metadata, runs
`session.run`, parses common YOLO output shapes, applies confidence filtering
and NMS, and returns source-frame tennis-ball boxes.

## What Is Real

- `apps/live3d` now depends on `onnxruntime-web`.
- `apps/live3d/src/onnx-yolo.ts` implements the real browser backend path.
- Frame preprocessing supports readable `HTMLVideoElement`, `HTMLCanvasElement`,
  `ImageBitmap`, and test RGBA frame sources.
- Postprocessing supports `[N,5+]`, `[1,N,5+]`, and `[1,5+,N]` YOLO output
  layouts for single-class `tennis_ball` detections.
- The backend reports blocked statuses for unsupported model runtime/path,
  missing or unreadable frame sources, session-load failures, inference failures,
  missing outputs, and unsupported output shapes.
- `apps/live3d/scripts/copy-static.js` copies ONNX Runtime Web wasm/mjs sidecar
  files into `dist/assets` for the browser bundle.

## Not Yet Physically Validated

The code implements a real browser ONNX backend path, but this wave did not
physically validate it with the exported tennis-ball ONNX model, live USB camera
frames, or the ROS/Gazebo pose and control chain. Do not treat this as completed
real catch-loop validation.

Wave 11 still needs to feed real left/right detections through stereo pairing,
triangulation, and prediction so the Live3D scene can leave fixture-only mode
when camera, model, and calibration artifacts are all ready.

## Validation

Passed:

```bash
cd apps/live3d && bun test
cd apps/live3d && bun run typecheck
cd apps/live3d && bun run build
git diff --check
```

Observed test result: 29 passing tests, 0 failures.
