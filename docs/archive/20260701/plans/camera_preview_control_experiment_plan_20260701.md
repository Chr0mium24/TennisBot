# Camera Preview Control Experiment Plan

## Goal

Empirically test how `auto_exposure`, `exposure_time_absolute`, `gain`, and
`brightness` affect the two USB cameras used by calibration preview.

## Procedure

1. Apply several V4L2 control combinations to `/dev/video0` and `/dev/video2`.
2. Wait briefly after each setting so auto exposure can settle.
3. Capture one frame per camera for each setting.
4. Record measured average brightness and final control values.
5. Keep captured images under `artifacts/calibration_experiments/preview_controls_20260701`.
