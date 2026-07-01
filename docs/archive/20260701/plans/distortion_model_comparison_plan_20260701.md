# Distortion Model Comparison Plan

Date: 2026-07-01

## Goal

Compare the 5-coefficient OpenCV distortion model against the rational distortion model on the current cam1/cam2 mono packages and the latest stereo capture session.

## Data

- Mono packages:
  - `artifacts/calibration/cam1`
  - `artifacts/calibration/cam2`
- Stereo session:
  - `tools/calibration/captures/local/stereo_charuco_20260701_111930_CST`

## Checks

- Stereo solve metrics with fixed intrinsics:
  - 5-coefficient model
  - rational model
- Per-image PnP reprojection RMS for the latest stereo images.
- Pixel-space undistortion differences between full rational coefficients and truncated 5 coefficients across the image.

## Output

Save numeric results in a Markdown result document and commit the documentation.
