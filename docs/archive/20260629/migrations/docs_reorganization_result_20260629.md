# Documentation Reorganization Result

Date: 2026-06-29

## Result

The documentation tree was reorganized into:

- `docs/README.md`
- `docs/current/`
- `docs/reports/`
- `docs/archive/YYYYMMDD/`

Current docs now describe the tracked mainline layout:

- `tools/calibration`
- `tools/yolo`
- `packages/core`
- `packages/contracts`
- `apps/live3d`

Historical migration, calibration, Live3D, probe, refactor, YOLO, and audit
documents were moved under dated archive directories.

## Notes

- The move preserved history and did not delete historical Markdown content.
- The biweekly report was moved to `docs/reports/` with its SVG assets.
- Current documentation now calls out the remaining calibration solve/export
  gap and the Live3D camera-frame versus court-frame limitation.

## Validation

- `git diff --check`
- `find docs -maxdepth 1 -mindepth 1 -printf '%f\n' | sort`
- `find docs/current -maxdepth 1 -type f | sort`

No code tests were required because this was a documentation-only change.
