# Multi-Agent Refactor Wave 3 Live3D Core Fixture Plan

Date: 2026-06-28

## Objective

Connect `apps/live3d` fixture mode to the new `packages/contracts` and
`packages/core` APIs without adding real camera capture or YOLO inference.

The result should prove the runtime wiring shape:

```text
fixture detections -> selectBestStereoPair -> triangulateStereoPair
-> predictTrajectory -> render fixture camera overlays and 3D prediction
```

This is still fixture mode. It must not be described as real-machine
validation.

## Branch

```text
refactor/live3d-core-fixture
```

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/live3d-core-fixture`
- Write scope:
  - `apps/live3d/**`
  - `docs/**`
- Read-only reference:
  - `packages/contracts/**`
  - `packages/core/**`
- Do not edit:
  - `packages/contracts/**`
  - `packages/core/**`
  - `BallTrajectoryLab/**`
  - `CameraCalibLab/**`
  - `TennisBallDetectorLab/**`
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `.gitmodules`

## Tasks

1. Update `apps/live3d` fixture data to use shared contract shapes:
   - `YoloDetection2D`;
   - `StereoCalibration`;
   - `TimestampedStereoDetectionPair`;
   - `TriangulatedBallPoint3D`;
   - `PredictionCurve`;
   - `LandingPoint`.
2. Use `selectBestStereoPair` from `packages/core` to choose a fixture stereo
   detection pair.
3. Use `triangulateStereoPair` from `packages/core` with fixture rectified
   projection matrices to produce a fixture 3D ball point.
4. Use `predictTrajectory` from `packages/core` with a short fixture point
   history to produce trajectory samples and landing point.
5. Render the computed fixture result in the existing UI instead of hand-coded
   scene points where practical.
6. Keep a visible fixture-mode warning. The UI and docs must state that this
   does not validate USB cameras, real YOLO inference, real calibration, or real
   prediction.
7. Add or update Bun tests to prove fixture construction calls the core flow and
   produces a stereo match, 3D point, prediction curve, and landing point.

## Implementation Notes

- Prefer importing the current source packages directly with relative imports
  until a root workspace/package resolver exists.
- Keep this as a frontend app shell. Do not add backend services.
- Do not start a long-running dev server unless needed for a manual smoke test;
  if started, stop it before reporting completion.
- Avoid broad CSS redesign. Only adjust UI text/data rendering needed for the
  computed fixture pipeline.

## Verification

Worker must run:

```bash
cd apps/live3d
bun run typecheck
bun test
bun run build

cd ../../packages/core
bun test
bun run typecheck

cd ../contracts
bun test
bun run typecheck
```

The lead will repeat relevant verification before merge.

## Acceptance Criteria

- Live3D fixture mode imports shared contracts/core functions.
- Fixture mode computes, rather than hard-codes, at least one stereo match,
  triangulated 3D point, prediction curve, and landing point.
- The fixture-mode warning remains visible and explicit.
- No real hardware or YOLO runtime is introduced.
- `packages/core` and `packages/contracts` are not changed in this branch.
- Existing `TennisBallDetectorLab` dirty state remains untouched.
