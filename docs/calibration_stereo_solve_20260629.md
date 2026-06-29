# Calibration Stereo Solve

Date: 2026-06-29

## Scope

This records the first standalone `tools/calibration` stereo solve path:

```text
mono solve cam1 + mono solve cam2 + stereo capture -> inspect -> detect-charuco -> calibrate stereo -> package verify
```

The run is a dry-run using rendered and perspective-warped DFOptix ChArUco
images. It proves the software path and stereo package writer, not physical
stereo calibration quality.

## Commands

```bash
cd tools/calibration

# cam2 mono package used by the stereo solve.
uv run tennisbot-calibration capture mono \
  --camera-id cam2 \
  --output ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run \
  --frame-count 5 \
  --interval-ms 0 \
  --width 960 \
  --height 640 \
  --dry-run
# The cam2 dry-run frames were replaced with rendered/perspective-warped DFOptix ChArUco target images.
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run \
  --output-report ../../docs/calibration_cam2_mono_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run \
  --output ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run/observations.json \
  --output-report ../../docs/calibration_charuco_detection_cam2_mono_solve_20260629.md
uv run tennisbot-calibration calibrate mono \
  --observations ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run/observations.json \
  --output ../../artifacts/calibration/cam2_mono_solve_dry_run \
  --min-views 3 \
  --max-rms-px 5

# Stereo solve.
uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --output ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run \
  --pair-count 5 \
  --interval-ms 0 \
  --width 960 \
  --height 640 \
  --dry-run
# The stereo dry-run frames were replaced with rendered/perspective-warped
# DFOptix ChArUco targets; right frames were offset horizontally.
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run \
  --output-report ../../docs/calibration_stereo_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run \
  --output ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run/observations.json \
  --output-report ../../docs/calibration_charuco_detection_stereo_solve_20260629.md
uv run tennisbot-calibration calibrate stereo \
  --observations ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run/observations.json \
  --left-mono ../../artifacts/calibration/cam1_mono_solve_dry_run \
  --right-mono ../../artifacts/calibration/cam2_mono_solve_dry_run \
  --output ../../artifacts/calibration/stereo_solve_dry_run \
  --min-pairs 3 \
  --max-rms-px 50
uv run tennisbot-calibration package verify \
  --path ../../artifacts/calibration/stereo_solve_dry_run
```

## Result

```text
tools/calibration tests: 19 passed.
cam2 mono solve: accepted=true, rms_reprojection_px=3.5345133067225127.
stereo capture inspect: accepted=true, 10/10 images read, no issues.
stereo detect-charuco: accepted=true, 10/10 views and 5/5 pairs accepted.
calibrate stereo: accepted=true, stereo_rms_reprojection_px=3.5982434312593963, baseline_m=0.03480523495236254.
package verify: accepted=true, package_kind=stereo, dry_run=true, hardware_validated=false.
```

## Artifacts

- cam2 capture quality report: `docs/calibration_cam2_mono_solve_capture_quality_20260629.md`
- cam2 ChArUco detection report: `docs/calibration_charuco_detection_cam2_mono_solve_20260629.md`
- stereo capture quality report: `docs/calibration_stereo_solve_capture_quality_20260629.md`
- stereo ChArUco detection report: `docs/calibration_charuco_detection_stereo_solve_20260629.md`
- ignored cam2 mono package: `artifacts/calibration/cam2_mono_solve_dry_run`
- ignored stereo package: `artifacts/calibration/stereo_solve_dry_run`

## Remaining Work

- Run the same stereo solve on real camera sessions after both mono packages and
  stereo observations pass real capture gates.
- Tighten stereo RMS, baseline, and rectification gates for real calibration
  evidence.
- Use the real accepted stereo package in Live3D and re-run hardware prediction
  validation with a visible tennis ball.
