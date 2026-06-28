# Multi-Agent Refactor Wave 9 Live3D YOLO Inference Plan

Date: 2026-06-29

Owner: worker subagent, lead review by main agent

Target branch: `refactor/live3d-yolo-inference`

## Goal

Add the Live3D-side YOLO inference data path without moving YOLO training,
annotation, export, or packaging code into the main runtime. `tools/yolo`
remains the standalone package producer; `apps/live3d` only consumes validated
runtime artifacts and camera frames.

Wave 9 is not allowed to claim real model inference unless a real backend is
implemented and verified. If no real backend is available in this wave, the UI
must report inference as blocked or adapter-only, not as live YOLO.

## Scope

- Add an app-local TypeScript inference adapter boundary in `apps/live3d/src`.
- Convert video-frame-sized backend outputs into the shared
  `YoloDetection2D` contract.
- Support independent left and right camera detection state.
- Make detection overlays render from runtime detection state rather than only
  from fixture detections.
- Keep fixture overlays clearly labelled when they are fixture data.
- Add tests with fake/injected inference backends; tests must not require USB
  cameras, real model files, browser permissions, or `onnxruntime-web`.

## Non-Goals

- Do not add YOLO training, dataset, annotation, or export logic to
  `apps/live3d`, `packages/core`, or `packages/contracts`.
- Do not change `tools/yolo` except for documentation if a handoff gap is
  discovered.
- Do not implement stereo 3D reconstruction from real detections in this wave.
- Do not remove fixture mode; fixture mode remains the safe no-hardware render
  path.

## Expected Design

- `apps/live3d/src/detections.ts`
  - Defines a small `YoloInferenceBackend` interface.
  - Defines detection runtime status types for `idle`, `blocked`, `running`,
    and `ready`/`updated` states.
  - Converts backend boxes into `YoloDetection2D`, including stable detection
    ids, camera id, frame id, timestamps, confidence, bbox, and center pixels.
  - Rejects or clamps malformed backend boxes in tests.
- `apps/live3d/src/main.ts`
  - Adds explicit Start/Stop YOLO controls or couples YOLO start to already
    opened camera streams only when artifact metadata is loaded.
  - Renders left/right detection status separately.
  - Overlays runtime detections when available; otherwise keeps fixture
    overlays labelled as fixture-only.
- Tests
  - Fake backend returns deterministic left/right tennis-ball boxes.
  - Blocked backend returns a status without throwing.
  - Overlay conversion is tested without DOM camera hardware.

## Acceptance Criteria

- `cd apps/live3d && bun test` passes.
- `cd apps/live3d && bun run typecheck` passes.
- `cd apps/live3d && bun run build` passes.
- No tracked changes under `tools/yolo` or submodules unless the lead approves
  a documentation-only handoff note.
- UI text never implies fixture detections are real YOLO inference.
- Result Markdown records what is real, what is adapter-only, and what remains
  for the ONNX backend wave.

## Follow-Up Waves

- Wave 10: implement a real browser ONNX Runtime Web backend for exported
  `model.onnx` packages, including preprocessing and postprocessing.
- Wave 11: feed real left/right detections through core stereo pairing,
  triangulation, and prediction so the 3D scene uses live detections and real
  calibration.
