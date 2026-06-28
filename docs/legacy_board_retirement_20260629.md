# Legacy Board Runtime Retirement

Date: 2026-06-29

## Scope

This records the removal of the old `TennisBotCV` submodule from the main
TennisBot repository.

Removed from the top-level repo:

```text
TennisBotCV
```

The `.gitmodules` entry for `TennisBotCV` was removed at the same time.

## Reason

The current architecture is local-machine-first:

```text
apps/live3d
packages/contracts
packages/core
tools/calibration
tools/yolo
artifacts/
```

`TennisBotCV` was a legacy integration shell. It included duplicated contracts,
generated board deployment bundles, historical run outputs, local workbench
wrappers, and RK3576/kernel bringup state. Those responsibilities are outside
the active runtime boundary.

## Preserved Owners

- Real USB camera + YOLO + 3D runtime: `apps/live3d`.
- Shared schemas and runtime algorithms: `packages/contracts` and
  `packages/core`.
- Calibration artifacts: `tools/calibration` plus ignored local outputs under
  `artifacts/calibration/`.
- YOLO artifacts: `tools/yolo` plus ignored local outputs under
  `artifacts/models/`.
- Simulation source remains in `TennisWebSim` until a separate `apps/sim`
  migration is done.

## Not Changed

- `TennisBallDetectorLab` was not touched; it still has pre-existing user-owned
  dirty state.
- `CameraCalibLab`, `BallTrajectoryLab`, and `TennisWebSim` remain as reference
  submodules for migration work.
- No board-side deployment service is part of the active TennisBot runtime.

## Verification

Commands:

```bash
git -C TennisBotCV status --short
git rm TennisBotCV
git status --short
```

Result:

```text
TennisBotCV was clean before removal.
The top-level gitlink and .gitmodules entry were removed.
The only unrelated dirty entry remains the pre-existing TennisBallDetectorLab
submodule state.
```
