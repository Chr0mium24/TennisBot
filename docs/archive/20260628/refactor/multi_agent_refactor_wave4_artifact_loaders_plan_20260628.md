# Multi-Agent Refactor Wave 4 Artifact Loaders Plan

Date: 2026-06-28

## Objective

Add runtime artifact validation and conversion helpers for:

- YOLO model packages produced by `tools/yolo`;
- stereo calibration packages produced by `tools/calibration`.

This wave should make the boundary explicit:

```text
artifact JSON files -> validation/conversion -> packages/contracts runtime shapes
```

It must not add real USB camera capture, YOLO inference, calibration solving, or
Live3D app integration.

## Branch

```text
refactor/artifact-loaders
```

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/artifact-loaders`
- Write scope:
  - `packages/contracts/**`
  - `packages/core/**`
  - `docs/**`
- Read-only reference:
  - `tools/yolo/MODEL_PACKAGE_CONTRACT.md`
  - `tools/calibration/artifact_contracts.md`
  - `apps/live3d/src/config.ts`
- Do not edit:
  - `apps/live3d/**`
  - `tools/yolo/**`
  - `tools/calibration/**`
  - `BallTrajectoryLab/**`
  - `CameraCalibLab/**`
  - `TennisBallDetectorLab/**`
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `.gitmodules`

## Tasks

1. Define raw artifact JSON types where useful:
   - YOLO `package.json`;
   - YOLO `labels.json`;
   - YOLO `preprocessing.json`;
   - YOLO `postprocessing.json`;
   - stereo calibration `package.json`;
   - `cam1.json` / `cam2.json`;
   - `stereo.json`;
   - `rectification.json`.
2. Add runtime validation helpers that return explicit success/failure results
   instead of throwing for ordinary invalid package data.
3. Add conversion helpers from snake_case artifact JSON to runtime contracts:
   - `CameraIntrinsics`;
   - `StereoCalibration`;
   - `RectifiedStereoProjectionMatrices`;
   - runtime YOLO model metadata.
4. Keep IO abstract. Prefer functions that accept already-parsed objects, plus
   a small `ArtifactJsonReader` interface if needed.
5. Make model file existence and SHA checks pluggable or represented as
   pending checks. Do not require real `.pt`, `.onnx`, or `.rknn` files in tests.
6. Add focused Bun tests with small inline fixtures for:
   - valid YOLO package metadata;
   - invalid YOLO package missing class `0 = tennis_ball`;
   - valid stereo calibration package;
   - rejected stereo calibration package where quality/verification is not
     accepted;
   - conversion from artifact matrix arrays to row-major contract matrices.
7. Update docs with loader responsibilities and what remains out of scope.

## Implementation Guidance

- Put pure conversion/validation code under `packages/core/src/artifacts.ts` or
  a small split such as `artifact-loaders.ts` if the file grows.
- If new contract types are required, add them under
  `packages/contracts/src/artifacts.ts` and export them from
  `packages/contracts/src/index.ts`.
- Do not import Node-only APIs unless the function name and tests make that
  environment explicit. Live3D is browser-oriented, so pure object validation is
  preferred for this wave.
- Error messages should identify the missing field or invalid value.

## Required Verification

The worker must run:

```bash
cd packages/contracts
bun test
bun run typecheck

cd ../core
bun test
bun run typecheck

git diff --check
git diff --name-only main..HEAD
```

## Acceptance Criteria

- Artifact loader APIs are pure and data-only.
- Valid inline YOLO fixture converts to runtime model metadata.
- Valid inline stereo calibration fixture converts to `StereoCalibration`.
- Invalid fixtures return rejected results with actionable messages.
- No large artifacts or generated outputs are committed.
- No edits occur outside `packages/contracts/**`, `packages/core/**`, and
  `docs/**`.
- Existing `TennisBallDetectorLab` dirty state remains untouched.

## Lead Review Notes

The lead should check:

- snake_case artifact JSON is converted explicitly to camelCase runtime
  contracts;
- matrix flattening is row-major and tested;
- accepted/rejected calibration quality gates are enforced;
- YOLO class `0 = tennis_ball` is enforced;
- loaders do not silently fall back to training directories or loose model
  files.
