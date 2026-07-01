# Stereo Rational Distortion Flag Fix Plan

Date: 2026-07-01

## Problem

Mono calibration uses OpenCV's rational distortion model, but stereo calibration was calling `cv2.stereoCalibrate` with only `CALIB_FIX_INTRINSIC`. In this mode OpenCV returned 5 distortion coefficients, which means the fixed stereo solve was not preserving the mono rational distortion model.

The current stereo session showed this directly:

- `CALIB_FIX_INTRINSIC`: stereo RMS `13.6201 px`
- `CALIB_FIX_INTRINSIC | CALIB_RATIONAL_MODEL`: stereo RMS `0.2121 px`

## Fix

- Use `CALIB_FIX_INTRINSIC | CALIB_RATIONAL_MODEL` for stereo extrinsic solve.
- Add test coverage that the stereo calibration flags preserve the rational model.
- Re-run the current stereo session solve-only to verify the output package.

## Verification

- Calibration unit tests with `uv`.
- `bun run scripts/calib.ts stereo --solve-only` on the latest stereo capture session.
