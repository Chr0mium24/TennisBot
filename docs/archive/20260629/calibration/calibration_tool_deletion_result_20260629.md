# Calibration Tool Deletion Result

Date: 2026-06-29

## Scope

Deleted the standalone `tools/calibration` Python package. Calibration now
uses the retained original OpenCV `desperate/CameraCalibLab` workflow when the
local archive is present. Runtime code continues to consume exported
calibration artifacts from `artifacts/calibration/...`.

## Changes

- Removed `tools/calibration/`.
- Updated `README.md` and current architecture/status docs so the active
  architecture no longer lists `tools/calibration`.
- Updated local operator and physical validation docs to point at
  `desperate/CameraCalibLab` instead of `tennisbot-calibration`.
- Updated `scripts/operator-preflight.ts` so stereo calibration preflight reads
  `artifacts/calibration/stereo_cam1_cam2/package.json` directly.
- Updated `scripts/physical-validation-status.ts` so next-action text no
  longer references the deleted CLI.

## Verification

- `rg "tools/calibration|tennisbot-calibration" README.md docs/current_architecture_20260629.md docs/current_status_20260629.md docs/local_runtime_operator_runbook_20260629.md docs/local_physical_validation_checklist_20260629.md scripts`
  returns only deletion-history mentions in `README.md` and
  `docs/current_architecture_20260629.md`.
- `bun scripts/operator-preflight.ts --help`: passed.
- `bun scripts/physical-validation-status.ts --help`: passed.
- `bun scripts/physical-validation-status.ts --output /tmp/tennisbot_physical_status.md --output-json /tmp/tennisbot_physical_status.json || true`:
  executed successfully and reports the expected remaining physical blocked
  gates.
- `bun build scripts/operator-preflight.ts --target bun --outfile /tmp/operator-preflight.js`:
  passed.
- `bun build scripts/physical-validation-status.ts --target bun --outfile /tmp/physical-validation-status.js`:
  passed.

## Notes

Historical docs still contain references to `tools/calibration` where they
record previous migration waves or validation runs. Those records were left
unchanged because they describe past work, not the current operator path.
