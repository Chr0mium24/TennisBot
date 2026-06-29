# Calibration Frontend Review Revert

Date: 2026-06-29

## Goal

Remove the new `tools/calibration/frontend/review` TypeScript/Bun calibration
review frontend from the active project surface and keep calibration capture on
the original `CameraCalibLab` OpenCV GUI.

## Change

- Reverted `tools/calibration/frontend/review` to its state before commit
  `994614a` by applying a path-level reverse patch.
- Removed current README and architecture references that instructed operators
  to run the calibration review frontend service.
- Removed the deleted frontend from `scripts/start-local-runtime.ts` and
  `scripts/operator-preflight.ts`.
- Updated physical-validation next-action text to point at CLI commands instead
  of the deleted web GUI tabs.
- Documented the retained OpenCV stereo ChArUco GUI command:
  `uv run camera-calib-lab capture stereo-charuco-auto-gui`.

## Notes

This does not modify the nested `CameraCalibLab` or `TennisBallDetectorLab`
working trees. Their existing local dirty state is left untouched.

## Verification

- `cd tools/calibration && uv run pytest -q`: passed, `22 passed`.
- `bun scripts/start-local-runtime.ts --no-build`: ran against the current
  local environment and no longer starts or prints the deleted calibration
  frontend.
