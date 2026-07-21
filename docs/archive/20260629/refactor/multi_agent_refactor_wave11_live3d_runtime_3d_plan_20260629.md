# Multi-Agent Refactor Wave 11 Live3D Runtime 3D Plan

Date: 2026-06-29

Owner: worker subagent, lead review by main agent

Target branch: `refactor/live3d-runtime-3d`

## Goal

Connect Live3D runtime detections to the existing core stereo and prediction
algorithms so the app can leave fixture-only 3D rendering when real camera
streams, a YOLO artifact, and a stereo calibration artifact are all available.

This wave completes the software-side flow:

1. Open two browser USB camera streams.
2. Run YOLO backend on left and right frames.
3. Select a stereo detection pair.
4. Triangulate a 3D ball point with loaded calibration.
5. Maintain a runtime point trail.
6. Generate a prediction curve and landing point once enough runtime points
   exist.

## Scope

- Add an app-local runtime scene module, for example
  `apps/live3d/src/runtime-scene.ts`.
- Use `packages/core` functions:
  - `selectBestStereoPair`
  - `triangulateStereoPair`
  - `predictTrajectory`
- Use loaded `StereoCalibrationArtifactLoadStatus` for triangulation. Do not
  use fixture calibration for runtime detections.
- Keep runtime point history across repeated YOLO runs in the same page session.
- Render runtime 3D ball/trail/prediction/landing when valid runtime state
  exists; otherwise render fixture scene with explicit fixture labels.
- Report clear runtime tracking statuses:
  - calibration missing/blocked;
  - no left/right detections;
  - no stereo pair selected;
  - triangulation failed;
  - one runtime point ready but prediction waiting for another point;
  - prediction ready.
- Use calibration camera ids for runtime detections when calibration is loaded
  so downstream diagnostics align with artifact metadata.
- Add deterministic tests with synthetic detections and calibration. Tests must
  not require cameras, ONNX files, browser permissions, or real ROS/chassis.

## Non-Goals

- Do not modify YOLO training, annotation, export, or packaging code.
- Do not modify calibration capture or calibration package export code.
- Do not claim real physical validation without running real USB cameras and
  exported artifacts.
- Do not add real ROS/chassis control or catch-loop replacement logic.

## Expected Design

- `Runtime3dState`
  - Contains latest pairing status, latest triangulated point, runtime trail,
    prediction curve, landing point, and user-facing status messages.
  - Has an initial idle state and a pure update function that consumes current
    left/right `YoloInferenceRuntimeStatus`, calibration status, previous state,
    and timestamp/frame id information.
- `apps/live3d/src/main.ts`
  - Updates runtime 3D state after YOLO inference finishes.
  - Passes runtime scene state into scene rendering.
  - Keeps fixture scene as fallback and labels it clearly.
- Tests
  - Valid left/right detections plus synthetic calibration produce a 3D point.
  - Two sequential runtime updates produce a prediction curve and landing point.
  - Missing calibration and no-pair cases return blocked/pending status without
    throwing.

## Acceptance Criteria

- `cd apps/live3d && bun test` passes.
- `cd apps/live3d && bun run typecheck` passes.
- `cd apps/live3d && bun run build` passes.
- `git diff --check` passes.
- Result Markdown records what is now connected end-to-end in software and what
  still needs physical validation.
- UI text does not present fixture fallback as real detections, real 3D, or real
  prediction.

## Follow-Up Validation

After Wave 11, the remaining work is physical validation rather than a major
architecture refactor:

- generate or copy real calibration and ONNX packages under `artifacts/`;
- run `apps/live3d` against two real USB cameras;
- validate browser ONNX inference on real frames;
- verify stereo 3D point stability and prediction quality;
- only then evaluate real ROS/chassis closed-loop catch behavior.
