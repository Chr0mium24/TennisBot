# Script Surface Simplification Plan

Date: 2026-06-30

## Goal

Reduce root-level operator scripts to one Live3D launcher and move camera
brightness inspection into the calibration tool boundary.

## Scope

- Move camera brightness checking from root `scripts/` into
  `tools/calibration` as a `camera-calib-lab` command.
- Replace `scripts/start-local-runtime.ts` with a single root Live3D launcher
  named `scripts/live3d.ts`.
- Remove root preflight and physical-validation helper scripts.
- Update current docs and README so they no longer advertise deleted root
  scripts.

## Non-Goals

- Do not delete historical archive records.
- Do not remove Live3D hardware verification under `apps/live3d`.
- Do not change ROS/Gazebo receiving-loop claims or add substitute receiving
  logic.

## Verification

- `cd tools/calibration && uv run camera-calib-lab camera brightness --help`
- `cd tools/calibration && uv run python -m unittest discover -s tests`
- `bun scripts/live3d.ts --help`
- `bun scripts/live3d.ts --status`
- `cd apps/live3d && bun test && bun run typecheck && bun run build`
