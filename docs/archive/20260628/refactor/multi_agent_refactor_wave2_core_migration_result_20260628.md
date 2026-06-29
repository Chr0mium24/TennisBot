# Multi-Agent Refactor Wave 2 Core Migration Result

Date: 2026-06-28

Lead agent: main thread

Source plan:
[`multi_agent_refactor_wave2_core_migration_plan_20260628.md`](multi_agent_refactor_wave2_core_migration_plan_20260628.md)

## Summary

Wave 2 core migration is merged into `main`. It replaces the initial
`packages/core` triangulation and prediction placeholders with data-only runtime
logic migrated from the pure parts of `BallTrajectoryLab`.

The migration intentionally keeps `BallTrajectoryLab` read-only and leaves
Kalman filtering for a later branch.

## Branch Results

| Branch | Worker commit | Lead review commit | Lead integration |
| --- | --- | --- | --- |
| `refactor/core-migration` | `ac9ab12` | `513169b` | `de23b59` |

The lead review commit added timestamp-delta filtering to stereo pairing. The
worker API already accepted `maxTimestampDeltaMs`, but the first implementation
did not reject stale left/right detection pairs.

## Runtime Core Added

`packages/core` now owns:

- rectified epipolar error;
- disparity;
- row-major 3x4 projection matrix reprojection;
- rectified stereo triangulation without OpenCV;
- average stereo reprojection diagnostics;
- timestamped stereo pair triangulation diagnostics;
- stereo detection pairing with timestamp, epipolar, disparity, confidence, and
  temporal-continuity scoring;
- projectile trajectory prediction with z as the vertical-up axis;
- optional landing point prediction.

`packages/contracts` now includes:

- `Matrix3x4`;
- rectified stereo projection matrices;
- stereo pairing diagnostics;
- triangulation diagnostics;
- optional stereo pair geometry diagnostics.

## Boundary Check

Changed paths are limited to:

- `docs/**`;
- `packages/contracts/**`;
- `packages/core/**`.

The following were not edited by this wave:

- `BallTrajectoryLab/**`;
- `CameraCalibLab/**`;
- `TennisBallDetectorLab/**`;
- `TennisWebSim/**`;
- `TennisBotCV/**`;
- `apps/live3d/**`;
- `.gitmodules`.

## Verification

Final verification on `main`:

```bash
cd packages/contracts
bun test
bun run typecheck
```

Result:

- `4 pass`
- `tsc --noEmit` passed

```bash
cd packages/core
bun test
bun run typecheck
```

Result:

- `13 pass`
- `tsc --noEmit` passed

```bash
cd apps/live3d
bun run typecheck
bun test
bun run build
```

Result:

- `2 pass`
- `tsc --noEmit` passed
- browser bundle built successfully

```bash
git diff --check HEAD~8..HEAD
```

Result:

- passed with no output

## Remaining Dirty State

The only remaining dirty top-level status after the merge is still:

```text
 m TennisBallDetectorLab
```

This is the pre-existing user-owned YOLO dataset/model state. It was not
modified, staged, or cleaned.

## Next Step

The next branch should connect `apps/live3d` fixture data to `packages/contracts`
and `packages/core` in fixture mode only:

```text
refactor/live3d-core-fixture
```

That branch should:

- import shared detection, calibration, 3D point, and prediction types;
- run fixture detections through `selectBestStereoPair`;
- triangulate a fixture pair through the new rectified projection matrices;
- call `predictTrajectory` from the resulting point history;
- keep fixture mode visibly non-validating;
- avoid real USB cameras and YOLO inference until artifact loaders and camera
  adapters exist.
