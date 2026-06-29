# Multi-Agent Refactor Wave 10 Live3D ONNX Backend Plan

Date: 2026-06-29

Owner: worker subagent, lead review by main agent

Target branch: `refactor/live3d-onnx-backend`

References:

- ONNX Runtime Web overview:
  <https://onnxruntime.ai/docs/tutorials/web/>
- ONNX Runtime Web app guide:
  <https://onnxruntime.ai/docs/tutorials/web/build-web-app.html>

## Goal

Implement a real browser ONNX Runtime Web backend behind the Wave 9
`YoloInferenceBackend` boundary. The backend must consume the validated
`tools/yolo` model package from `/artifacts/models/tennis_ball_yolo`, load the
selected ONNX model file, preprocess a real video frame, run `session.run`, and
postprocess model output into tennis-ball boxes.

## Scope

- Add `onnxruntime-web` to `apps/live3d` with `bun`.
- Add an app-local backend module, for example `apps/live3d/src/onnx-yolo.ts`.
- Keep the backend behind the existing `YoloInferenceBackend` interface from
  `apps/live3d/src/detections.ts`.
- Resolve the model URL from `YoloArtifactLoadStatus.packagePath` and
  `YoloModelArtifactMetadata.modelPath`.
- Initialize the ONNX session lazily and only once per backend instance.
- Preprocess `HTMLVideoElement`, `HTMLCanvasElement`, `ImageBitmap`, or a test
  canvas-like source into RGB float tensor data using the package
  preprocessing metadata.
- Implement letterbox metadata needed to map model-space detections back to
  source frame pixels.
- Postprocess common YOLO ONNX outputs for single-class `tennis_ball`,
  applying confidence threshold, max detections, and NMS.
- Surface clear blocked statuses when the model package has no ONNX entry,
  the browser cannot provide a readable frame, the ONNX session cannot load,
  or the output shape is unsupported.
- Update UI wiring so a loaded YOLO artifact uses the real ONNX backend by
  default. Keep blocked state explicit when no model package exists.

## Non-Goals

- Do not add YOLO training, annotation, export, or dataset code to Live3D.
- Do not modify `tools/yolo` unless a documentation-only handoff note is
  clearly needed.
- Do not implement RKNN, PT/Ultralytics, server-side inference, or board-device
  inference.
- Do not wire runtime detections into 3D stereo prediction in this wave.

## Expected Design

- `OnnxYoloInferenceBackend`
  - Accepts artifact metadata and package path.
  - Verifies `metadata.modelRuntime === "onnxruntime"` or selected model key is
    ONNX-compatible before attempting to load.
  - Creates `ort.InferenceSession` from the artifact model URL.
  - Builds input tensor shape `[1, 3, height, width]` unless the session input
    metadata requires a compatible static shape.
  - Uses canvas draw/readback for video-frame preprocessing.
  - Returns `BackendYoloBox[]` in source frame pixels.
- Unit tests
  - Use a fake ORT module/session; no real ONNX file is required for unit tests.
  - Test preprocessing letterbox mapping with deterministic image data.
  - Test postprocessing for at least one supported YOLO output shape.
  - Test blocked states for unsupported runtime and unsupported output shape.

## Acceptance Criteria

- `cd apps/live3d && bun test` passes.
- `cd apps/live3d && bun run typecheck` passes.
- `cd apps/live3d && bun run build` passes.
- `git diff --check` passes.
- `apps/live3d/package.json` and `apps/live3d/bun.lock` record the ONNX Runtime
  Web dependency.
- Result Markdown states whether real browser inference is implemented and
  what still requires physical model/camera validation.

## Follow-Up Wave

- Wave 11: feed real left/right detections through core stereo pairing,
  triangulation, and prediction so Live3D's 3D scene leaves fixture-only mode
  when real camera, model, and calibration artifacts are all ready.
