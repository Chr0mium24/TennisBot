# Camera Preview Controls Plan

Date: 2026-06-30

## Goal

Add a project-level camera preview/debug command before calibration so operators
can see live camera video and adjust shutter/exposure time plus gain without
typing low-level `v4l2-ctl` commands.

## Scope

- Add a `camera preview` command to `tools/calibration`.
- Expose it from the root wrapper as:
  - `bun scripts/calib.ts preview`
  - `bun scripts/calib.ts preview cam1`
  - `bun scripts/calib.ts preview cam2`
- Default stereo preview devices to `/dev/video0,/dev/video2`.
- Provide OpenCV video preview with trackbars for:
  - `exposure_time_absolute`
  - `gain`
- Use `v4l2-ctl` for UVC control writes.
- Update current operator docs and command help.

## Non-Goals

- Do not change calibration solving or capture logic.
- Do not create a browser replacement for Live3D.
- Do not run real GUI preview in automated verification.

## Verification

- `bun scripts/calib.ts preview --dry-run`
- `bun scripts/calib.ts preview cam1 --dry-run`
- `bun scripts/calib.ts preview cam2 --dry-run`
- `cd tools/calibration && uv run python -m unittest discover -s tests`
- `git diff --check`
