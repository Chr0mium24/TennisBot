# Distortion Model Comparison Result

Date: 2026-07-01

## Data

- Mono cam1 session: `tools/calibration/captures/local/cam1_charuco_20260701_105937_CST`
- Mono cam2 session: `tools/calibration/captures/local/cam2_charuco_20260701_111120_CST`
- Stereo session: `tools/calibration/captures/local/stereo_charuco_20260701_111930_CST`
- Stereo pairs: `38`
- Points per pair: `104`
- Image size: `1280 x 720`

## Current Package Coefficients

Both current mono packages use OpenCV rational distortion with 14 coefficients.

| Camera | First 8 coefficients |
|---|---|
| cam1 | `0.52115884, 0.57116612, 0.00012813, -0.00004294, -0.04332795, 0.45265116, 0.61565887, -0.03261367` |
| cam2 | `0.23798665, 0.12871807, -0.00014993, 0.00011946, -0.08942547, 0.16723333, 0.20951894, -0.10686774` |

## Bug Reproduction

This compares the previous bad stereo behavior: using the rational mono package but solving stereo as a 5-coefficient model.

| Model used in stereo | Stereo RMS | Epipolar RMS | Baseline | Dist coeffs used |
|---|---:|---:|---:|---:|
| Truncated 5-coefficient | `13.6201 px` | `30.9051 px` | `0.2349 m` | `5` |
| Full rational | `0.2121 px` | `0.2568 px` | `0.1650 m` | `14` |

With truncated coefficients, per-image PnP RMS on the stereo images also becomes very large:

| Model | Left PnP mean RMS | Right PnP mean RMS |
|---|---:|---:|
| Truncated 5-coefficient | `7.5791 px` | `3.5459 px` |
| Full rational | `0.1326 px` | `0.1225 px` |

The reason is that the first 5 rational coefficients are not a valid standalone 5-coefficient calibration. At the image edges, undistortion differs by hundreds of pixels:

| Camera | Mean delta | P95 delta | Max delta |
|---|---:|---:|---:|
| cam1 | `182.95 px` | `524.02 px` | `654.77 px` |
| cam2 | `74.88 px` | `194.97 px` | `249.49 px` |

## Fair Model Comparison

This recalibrates mono from the same source images once with a real 5-coefficient OpenCV model and once with rational, then solves stereo with matching fixed intrinsics.

### Mono

| Camera | Model | Mono RMS | Dist coeffs | fx | fy |
|---|---|---:|---:|---:|---:|
| cam1 | 5-coefficient | `0.2331 px` | `5` | `471.2072` | `471.1322` |
| cam1 | rational | `0.1777 px` | `14` | `465.7063` | `465.8526` |
| cam2 | 5-coefficient | `0.2308 px` | `5` | `471.6314` | `471.3610` |
| cam2 | rational | `0.1801 px` | `14` | `466.6010` | `466.4515` |

### Stereo

| Mono model | Stereo RMS | Epipolar RMS | Rectified y p95 | Baseline |
|---|---:|---:|---:|---:|
| 5-coefficient | `0.3091 px` | `0.3568 px` | `0.6857 px` | `0.1659 m` |
| rational | `0.2121 px` | `0.2568 px` | `0.4296 px` | `0.1650 m` |

The 5-coefficient model is usable when calibrated consistently from scratch, but rational is better for these lenses and images.

## Epipolar Metric Fix

The previous `epipolar_rms_px=2.1764` was computed from raw distorted pixel points. That overstates the error for rational distortion.

The solver now computes epipolar RMS after undistorting points and evaluating the essential-matrix constraint in normalized coordinates, converted back to pixels by average focal length.

Current accepted stereo package after the metric fix:

```text
solve status=accepted pairs=38/38 points=left:104 right:104 rms=0.2121px epipolar=0.2568px images=left:/home/cr/Codes/TennisBot/tools/calibration/captures/local/stereo_charuco_20260701_111930_CST/left/view*/image.png right:/home/cr/Codes/TennisBot/tools/calibration/captures/local/stereo_charuco_20260701_111930_CST/right/view*/image.png result=/home/cr/Codes/TennisBot/artifacts/calibration/stereo_cam1_cam2
```

## Verification

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

```text
21 passed in 0.62s
```
