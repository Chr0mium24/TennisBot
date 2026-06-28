# Calibration Mono Solve

Date: 2026-06-29

## Scope

This records the first standalone `tools/calibration` mono solve path:

```text
capture mono -> capture inspect -> capture detect-charuco -> calibrate mono -> package verify
```

The run is a dry-run using rendered and perspective-warped DFOptix ChArUco
images. It proves the software path and package writer, not physical calibration
quality.

## Commands

```bash
cd tools/calibration
uv run tennisbot-calibration capture mono \
  --camera-id cam1 \
  --output ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run \
  --frame-count 5 \
  --interval-ms 0 \
  --width 960 \
  --height 640 \
  --dry-run

# The dry-run frames were replaced with rendered/perspective-warped DFOptix
# ChArUco target images before inspection and detection.

uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run \
  --output-report ../../docs/calibration_mono_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run \
  --output ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run/observations.json \
  --output-report ../../docs/calibration_charuco_detection_mono_solve_20260629.md
uv run tennisbot-calibration calibrate mono \
  --observations ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run/observations.json \
  --output ../../artifacts/calibration/cam1_mono_solve_dry_run \
  --min-views 3 \
  --max-rms-px 5
uv run tennisbot-calibration package verify \
  --path ../../artifacts/calibration/cam1_mono_solve_dry_run
```

## Result

```text
tools/calibration tests: 18 passed.
capture inspect: accepted=true, 5/5 images read, no issues.
capture detect-charuco: accepted=true, 5/5 views accepted, 104 corners and 63 markers per view.
calibrate mono: accepted=true, rms_reprojection_px=3.551100557082021, accepted_view_count=5.
package verify: accepted=true, package_kind=mono, dry_run=true, hardware_validated=false.
```

## Artifacts

- Capture quality report: `docs/calibration_mono_solve_capture_quality_20260629.md`
- ChArUco detection report: `docs/calibration_charuco_detection_mono_solve_20260629.md`
- Ignored mono package: `artifacts/calibration/cam1_mono_solve_dry_run`

## Remaining Work

- Run the same mono solve on real camera sessions after `capture inspect` and
  `capture detect-charuco` pass with a visible target.
- Tighten the default RMS gate for real calibration evidence.
- Add stereo solve from accepted stereo observations plus accepted mono
  intrinsics.
