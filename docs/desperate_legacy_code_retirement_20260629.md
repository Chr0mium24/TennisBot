# Desperate Legacy Code Retirement

Date: 2026-06-29

## Plan

- Remove the four legacy lab directories from the parent repository submodule
  graph.
- Keep their checked-out source trees locally under `desperate/` for reference.
- Ignore `desperate/` from the parent repository so future work does not stage
  legacy code or nested Git state.
- Update current operator documentation and scripts to point at the local
  `desperate/` archive when they mention legacy tools.

## Result

- Deleted `.gitmodules`.
- Removed the parent Git index entries for:
  - `BallTrajectoryLab`
  - `CameraCalibLab`
  - `TennisBallDetectorLab`
  - `TennisWebSim`
- Preserved the local source trees at:
  - `desperate/BallTrajectoryLab`
  - `desperate/CameraCalibLab`
  - `desperate/TennisBallDetectorLab`
  - `desperate/TennisWebSim`
- Removed nested `.git` metadata from those local directories, including the
  nested `Tennis_Robot_Chassis` checkout under `desperate/TennisWebSim`.
- Added `desperate/` to `.gitignore`.

## Operational Note

`desperate/` is now a local-only code archive. The active TennisBot runtime
must continue to live in `apps/`, `packages/`, `tools/`, `docs/`, and
`scripts/`. If a legacy command is still needed on this machine, run it from
the matching directory under `desperate/`.

## Verification

- `git submodule status --recursive`: no submodules listed.
- `git ls-files -s | awk '$1=="160000" {print $4}'`: no gitlinks listed.
- `find desperate -path '*/.git' -maxdepth 4 -print`: no nested Git metadata
  listed.
- `git diff --check`: passed.
- `bun scripts/start-local-runtime.ts --status`: passed; Live3D was ready at
  `http://127.0.0.1:5178/`.
- `bun scripts/physical-validation-status.ts --output /tmp/tennisbot_physical_validation_status_check.md --output-json /tmp/tennisbot_physical_validation_status_check.json`:
  ran and wrote reports; exit code was 1 because existing physical validation
  gates are still incomplete.
