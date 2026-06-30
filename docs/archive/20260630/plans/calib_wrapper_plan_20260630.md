# Calib Wrapper Plan

Date: 2026-06-30

## Goal

Add a short root-level calibration wrapper so operators do not need to type long
`tools/calibration` commands for common camera and calibration flows.

## Scope

- Add `scripts/calib.ts`.
- Support:
  - `bun scripts/calib.ts brightness`
  - `bun scripts/calib.ts mono cam1`
  - `bun scripts/calib.ts mono cam2`
  - `bun scripts/calib.ts stereo`
- Keep defaults aligned with the current rig:
  - cam1: `/dev/video0`
  - cam2: `/dev/video2`
  - stereo output: `artifacts/calibration/stereo_cam1_cam2`
- Support `--capture-only`, `--solve-only`, and `--dry-run` for safer operation.
- Update current operator docs.

## Non-Goals

- Do not change calibration math.
- Do not alter ROS/Gazebo receiving-loop requirements.
- Do not touch historical archive records except this plan and the result.

## Verification

- `bun scripts/calib.ts --help`
- `bun scripts/calib.ts brightness --dry-run`
- `bun scripts/calib.ts mono cam1 --dry-run`
- `bun scripts/calib.ts mono cam2 --dry-run`
- `bun scripts/calib.ts stereo --dry-run`
