# Scripts UV Migration Plan

Date: 2026-07-12

## Goal

Migrate repository-root operator launchers from Bun/TypeScript entrypoints to
Python scripts that can be run with `uv run scripts/*.py`.

## Scope

- Replace root launcher entrypoints:
  - `scripts/yolo.ts` -> `scripts/yolo.py`
  - `scripts/calib.ts` -> `scripts/calib.py`
  - `scripts/stereo.ts` -> `scripts/stereo.py`
  - `scripts/vision-runtime.ts` -> `scripts/vision-runtime.py`
  - `scripts/check-chassis-position.ts` -> `scripts/check-chassis-position.py`
- Move shared camera control behavior into `scripts/camera_controls.py`.
- Keep Bun for TypeScript packages and the stereo replay frontend internals.
- Update current operator documentation from `bun scripts/*.ts` to
  `uv run scripts/*.py`.

## Non-Goals

- Do not rewrite `packages/contracts`, `packages/core`, or
  `tools/stereo/web/replay` away from TypeScript/Bun.
- Do not change real ROS/chassis runtime behavior or add local catch-loop fallback
  logic.
- Do not change calibration, stereo, or YOLO tool internals beyond launcher
  invocation.

## Verification

- Run help commands for every migrated script.
- Run safe dry-run commands for calibration, stereo, and vision runtime.
- Run Python compile checks for the new root scripts.
- Run representative existing Python and TypeScript checks where practical.
