# Multi-Agent Refactor Wave 2 Core Migration Plan

Date: 2026-06-28

## Objective

Continue the simplified architecture refactor with a single focused branch:

```text
refactor/core-migration
```

This branch migrates pure runtime math from `BallTrajectoryLab` into
`packages/core` and keeps all tool, dataset, calibration, simulation, and legacy
source trees untouched.

## Why One Branch

Core migration will touch `packages/contracts` and `packages/core`, which are
shared foundations for later `apps/live3d`, `apps/sim`, YOLO, and calibration
work. Running multiple code-edit branches against those files would create
unnecessary conflicts. This wave uses one worker and one lead reviewer.

## Current Constraints

- `TennisBallDetectorLab` has user-owned dirty dataset/model changes. Do not
  edit, move, stage, or clean that submodule.
- `CameraCalibLab` remains the current working calibration implementation. Do
  not move or edit it in this wave.
- `BallTrajectoryLab` is read-only reference material in this wave. Do not move
  or edit its files.
- `apps/live3d` remains fixture-mode UI. Do not claim real camera validation.

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/core-migration`
- Write scope:
  - `packages/contracts/**`
  - `packages/core/**`
  - `docs/**`
- Read-only reference:
  - `BallTrajectoryLab/src/ball_trajectory_lab/stereo_geometry.py`
  - `BallTrajectoryLab/src/ball_trajectory_lab/stereo_fusion.py`
  - `BallTrajectoryLab/src/ball_trajectory_lab/predictor_3d.py`
  - `BallTrajectoryLab/src/ball_trajectory_lab/stereo_types.py`
  - `BallTrajectoryLab/src/ball_trajectory_lab/types.py`
- Do not edit:
  - `BallTrajectoryLab/**`
  - `CameraCalibLab/**`
  - `TennisBallDetectorLab/**`
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `apps/live3d/**`
  - `.gitmodules`

## Implementation Scope

### Geometry

Port pure stereo geometry from `BallTrajectoryLab/stereo_geometry.py`:

- rectified epipolar error;
- disparity;
- 3D point reprojection through 3x4 projection matrices;
- average stereo reprojection error;
- rectified stereo triangulation without OpenCV.

The TypeScript implementation should not depend on OpenCV, NumPy, browser APIs,
or frontend code.

Add or extend contracts as needed for:

- `Matrix3x4`;
- rectified stereo projection matrices;
- triangulation diagnostics.

### Stereo Pairing

Port the simple matching policy from `BallTrajectoryLab/stereo_fusion.py`:

- filter candidate pairs by epipolar error;
- filter by min/max disparity;
- score candidates with confidence and optional temporal continuity;
- return the best match as plain data.

This can be stateless initially, or expose a small matcher class. Keep the API
data-only.

### Prediction

Replace the placeholder in `packages/core/src/prediction.ts` with the simple
projectile prediction behavior from `BallTrajectoryLab/predictor_3d.py`:

- compute future point at a horizon;
- solve landing time on a configurable vertical axis/surface;
- produce trajectory samples;
- return a `PredictionCurve` and optional `LandingPoint`.

Coordinate convention must be explicit in docs/tests. Use the existing contract
fields and avoid UI-specific assumptions.

### Not In Scope

Do not migrate Kalman state estimation in this branch unless the worker finishes
the above with clean tests and no broader API churn. Kalman migration can be a
later branch.

Do not migrate:

- dataset/session readers;
- OpenCV rendering;
- HTML report generation;
- calibration package loading beyond data contracts;
- simulation-specific Three.js math;
- YOLO inference.

## Required Tests

Add focused Bun tests covering:

- rectified epipolar error;
- disparity;
- reprojection through known 3x4 matrices;
- triangulation of a known rectified stereo point;
- reprojection error for the triangulated point;
- stereo pairing with at least two candidate pairs;
- projectile prediction with expected landing time and landing point;
- explicit no-landing or invalid-input behavior where applicable.

Keep fixtures small and inline.

## Required Verification

The worker must run:

```bash
cd packages/contracts
bun test
bun run typecheck

cd ../core
bun test
bun run typecheck
```

The lead will repeat these commands before merge.

## Acceptance Criteria

- `triangulateStereoPair` no longer returns `not-implemented` for valid
  rectified projection inputs.
- `predictTrajectory` no longer returns `not-implemented` for enough valid 3D
  points or state inputs.
- All new APIs are plain data functions/classes under `packages/core`.
- `packages/core` does not import from any tool, app, or child submodule.
- `BallTrajectoryLab` remains unchanged.
- The dirty `TennisBallDetectorLab` submodule remains untouched.
- The worker commits its branch and reports changed files plus verification
  results.

## Lead Review Notes

The lead should pay special attention to:

- coordinate naming consistency between artifact docs and runtime contracts;
- whether projection matrix conventions are documented as row-major;
- whether prediction treats vertical axis consistently;
- whether placeholder tests were replaced rather than merely added around
  unimplemented behavior;
- whether the migration remains small enough to review.

If the worker expands into Kalman filtering or app integration, reject that part
and split it into a later branch.
