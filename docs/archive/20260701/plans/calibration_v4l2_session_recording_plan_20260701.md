# Calibration V4L2 Session Recording Plan

Date: 2026-07-01

## Goal

Record the active V4L2 camera controls automatically in every ChArUco calibration capture session so exposure-related state is preserved with the images.

## Scope

- Use one shared V4L2 control parser/reader for preview and capture.
- Add a compact `v4l2_controls` snapshot to the camera metadata in `session.json`.
- Keep `manifest.json` aligned with the same camera metadata.
- Record the controls relevant to the current calibration workflow: `auto_exposure`, `exposure_time_absolute`, `brightness`, and `gain` when the device reports them.
- Leave solve parsing unchanged; controls are capture metadata and should not create another solve path.

## Verification

- Add unit coverage for V4L2 snapshot serialization and session camera metadata.
- Run the calibration test suite with `uv`.
