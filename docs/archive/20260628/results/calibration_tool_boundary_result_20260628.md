# Calibration Tool Boundary Result

Date: 2026-06-28

Branch: `refactor/calibration-tool-boundary`

## Plan

1. Create `tools/calibration` as a documentation-only boundary for Wave 1.
2. Map current `CameraCalibLab` commands to the target calibration tool
   responsibilities.
3. Define mono and stereo calibration package contracts for runtime consumers.
4. Record a migration checklist for moving `CameraCalibLab` in a later wave.
5. Verify the branch changes are limited to `tools/calibration/**` and `docs/**`.

## Result

- Added `tools/calibration/README.md` with ownership boundaries, target layout,
  current-to-target command mapping, runtime artifact roots, and a migration
  checklist.
- Added `tools/calibration/artifact_contracts.md` with minimum mono and stereo
  package file layouts and required JSON fields.
- Kept `CameraCalibLab` as a read-only reference. No files under
  `CameraCalibLab/**` were moved or edited.

## Migration Checklist

- [ ] Freeze the current `CameraCalibLab` baseline and record its commit.
- [ ] Confirm `uv run pytest -q` passes inside `CameraCalibLab`.
- [ ] Confirm `cd frontend/review && bun test && bun run build` passes inside
      `CameraCalibLab`.
- [ ] Copy implementation files into `tools/calibration` without changing
      behavior.
- [ ] Preserve `uv` for Python and `bun` plus TypeScript for the review
      frontend.
- [ ] Keep generated captures, runs, and calibration packages ignored by git.
- [ ] Add contract tests for mono packages under `artifacts/calibration/cam1`
      and `artifacts/calibration/cam2`.
- [ ] Add contract tests for stereo packages under
      `artifacts/calibration/stereo_cam1_cam2`.
- [ ] Update `apps/live3d` documentation to load calibration packages only from
      artifact directories.
- [ ] Remove or archive `CameraCalibLab` only after the migrated tool passes
      verification and the later-wave move is approved.

## Verification

- `git diff --check`: passed, no whitespace errors.
- `git status --short -- CameraCalibLab`: passed, no changes reported.
- `find tools -maxdepth 3 -type f | sort`: confirmed this branch's calibration
  additions are limited to `tools/calibration/README.md` and
  `tools/calibration/artifact_contracts.md`.
- Final staged-file and commit verification are recorded in the worker final
  report.
