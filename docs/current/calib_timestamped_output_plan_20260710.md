# Calib Timestamped Output Plan

Date: 2026-07-10

## Goal

Prevent the root `scripts/calib.ts` helper from overwriting existing calibration
packages during the normal mono and stereo workflow.

## Plan

- Change default mono outputs from fixed `artifacts/calibration/cam1` and
  `artifacts/calibration/cam2` to timestamped package directories.
- Change default stereo output from fixed `artifacts/calibration/stereo_cam1_cam2`
  to a timestamped package directory.
- Keep `bun scripts/calib.ts mono cam1`, `mono cam2`, then `stereo` as the
  normal workflow by having stereo select the latest accepted mono packages.
- Leave explicit `--output` available for deliberately writing fixed runtime
  paths.
- Update current operator documentation and verify the generated dry-run
  commands.

## Non-Goals

- Do not change calibration math or package schema.
- Do not alter ROS/Gazebo validation requirements.
- Do not automatically repoint the runtime config to a newly generated package.
