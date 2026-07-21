# Multi-Agent Refactor Wave 10 Live3D ONNX Backend Review

Date: 2026-06-29

Worker branch: `refactor/live3d-onnx-backend`

Merged commit: `1f742c7 Merge Live3D ONNX backend`

## Findings

- No unresolved blocking findings after lead review.
- Resolved during review: lead fix `2d1011f` configured ORT wasm sidecar loading
  from `/assets/`, served `.mjs` and `.wasm` with browser-compatible MIME types,
  required both `runtime=onnxruntime` and a `.onnx` model path, blocked
  multi-class ONNX rows for the current single-class runtime, combined
  objectness and class score for `[1,N,6]` output, and clipped decoded boxes at
  source-frame boundaries.

## Accepted Scope

- Live3D now depends on `onnxruntime-web`.
- `OnnxYoloInferenceBackend` implements a real browser backend path behind the
  existing `YoloInferenceBackend` interface.
- The backend lazily creates an ORT session from the validated model package,
  preprocesses readable frames into letterboxed NCHW float tensors, runs
  `session.run`, and postprocesses supported single-class YOLO outputs.
- The UI defaults to the ONNX backend when the YOLO artifact is loaded and keeps
  blocked status explicit when the artifact is unavailable or incompatible.

## Verification

```text
cd apps/live3d
bun test
```

Result: 33 passing tests, 0 failures.

```text
cd apps/live3d
bun run typecheck
```

Result: `tsc --noEmit` completed successfully.

```text
cd apps/live3d
bun run build
```

Result: typecheck, browser bundle, and static copy completed successfully.

```text
git diff --check HEAD~1..HEAD
```

Result: clean.

Port check for `5178`, `4173`, and `8765`: no listener left running.

## Residual Risk

- The real ONNX backend code path is implemented but not physically validated
  with the exported tennis-ball ONNX model and real USB camera frames.
- Runtime detections still do not drive stereo pairing, triangulation, or
  prediction. That remains Wave 11.
- real ROS/chassis closed-loop catch validation remains out of scope for this wave.
