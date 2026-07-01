# Stereo Rational Distortion Flag Fix Result

Date: 2026-07-01

## Diagnosis

The bad stereo result was caused by a solver flag mismatch, not by the captured images.

Mono calibration uses OpenCV's rational distortion model. The stereo solve fixed the mono intrinsics but did not pass `CALIB_RATIONAL_MODEL` to `cv2.stereoCalibrate`, so OpenCV reduced the fixed distortion model to 5 coefficients.

On the same stereo session:

| Flags | Stereo RMS | Epipolar RMS | Baseline |
|---|---:|---:|---:|
| `CALIB_FIX_INTRINSIC` | `13.6201 px` | `30.9051 px` | `0.2349 m` |
| `CALIB_FIX_INTRINSIC | CALIB_RATIONAL_MODEL` | `0.2121 px` | `2.1764 px` | `0.1650 m` |

Individual per-image PnP checks were low error, around `0.12-0.13 px`, so the left/right frames and detections were usable.

## Changes

- Stereo solve now uses `CALIB_FIX_INTRINSIC | CALIB_RATIONAL_MODEL`.
- Added unit coverage for the stereo calibration flags.

## Verification

Unit tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

```text
20 passed in 0.58s
```

Current stereo solve:

```bash
bun run scripts/calib.ts stereo --solve-only
```

Result:

```text
solve status=accepted pairs=38/38 points=left:104 right:104 rms=0.2121px epipolar=2.1764px warning=runtime_quality images=left:/home/cr/Codes/TennisBot/tools/calibration/captures/local/stereo_charuco_20260701_111930_CST/left/view*/image.png right:/home/cr/Codes/TennisBot/tools/calibration/captures/local/stereo_charuco_20260701_111930_CST/right/view*/image.png result=/home/cr/Codes/TennisBot/artifacts/calibration/stereo_cam1_cam2
```

The package is accepted. The remaining runtime warning is only that epipolar RMS `2.1764 px` is slightly above the `2.0 px` review threshold.
