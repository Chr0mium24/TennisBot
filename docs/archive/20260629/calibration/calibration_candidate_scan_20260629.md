# CameraCalibLab Calibration Candidate Scan

- root: ../../CameraCalibLab/runs/calibrations
- candidate_files: 17
- mono_candidates: 14
- stereo_candidates: 3
- skipped_files: 0

## Recommended Stereo Candidate

- path: `dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622/calibration.json`
- accepted: True
- warning_count: 1
- score: 1005.243865
- stereo_rms_px: 0.42365210023675176
- epipolar_rms_px: 4.3304497343502
- rectification_y_p95_px: 0.8301635742187499
- baseline_m: 0.05248616443700974
- accepted_pairs: 33
- matched_point_count_min: 104
- warnings:
  - epipolar_rms_px=4.330 exceeds runtime-quality review threshold 2.000

## Top Stereo Candidates

| rank | path | accepted | warnings | stereo_rms_px | epipolar_rms_px | rectification_y_p95_px | baseline_m | score |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | `dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622/calibration.json` | True | 1 | 0.423652 | 4.33045 | 0.830164 | 0.0524862 | 1005.243865 |
| 2 | `dfoptix_charuco_stereo_auto/calibration.json` | True | 3 | 5.35448 | 4.38362 | 6.65809 | 0.0556394 | 3016.055787 |
| 3 | `dfoptix_charuco_stereo_auto_fixed_intrinsics_20260622/calibration.json` | True | 3 | 23.4868 | 30.8016 | 19.3042 | 0.0677879 | 3073.252101 |

## Top Mono Candidates

| rank | path | accepted | calibration_rms_px | accepted_views | score |
| --- | --- | --- | ---: | ---: | ---: |
| 1 | `dfoptix_charuco_auto_combined_rational_20260620_top_right/calibration.json` | True | 0.202531 | 109 | 0.093531 |
| 2 | `dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7/calibration.json` | True | 0.202531 | 109 | 0.093531 |
| 3 | `dfoptix_charuco_auto_20260620_131207/calibration.json` | True | 0.170201 | 34 | 0.136201 |
| 4 | `dfoptix_charuco_auto_combined_rational_20260619/calibration.json` | True | 0.212529 | 75 | 0.137529 |
| 5 | `dfoptix_charuco_auto/calibration.json` | True | 0.240391 | 31 | 0.209391 |
| 6 | `dfoptix_charuco_auto_cam2/calibration.json` | True | 0.31812 | 35 | 0.283120 |
| 7 | `dfoptix_charuco_auto_cam2_current_rational_20260622/calibration.json` | True | 0.31812 | 35 | 0.283120 |
| 8 | `dfoptix_charuco_auto_20260619_091453/calibration.json` | True | 0.494337 | 44 | 0.450337 |
| 9 | `charuco_locked_20260617_resampled17/calibration.json` | True | 0.969458 | 17 | 0.952458 |
| 10 | `charuco_locked_20260617_filtered/calibration.json` | True | 1.07575 | 20 | 1.055752 |
| 11 | `charuco_zip_20260617/calibration.json` | True | 1.25148 | 9 | 1.242476 |
| 12 | `charuco_locked_20260617/calibration.json` | True | 1.721 | 21 | 1.700005 |
