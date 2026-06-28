# Calibration Capture Session Flow

Date: 2026-06-29

## Scope

This records the first standalone `tools/calibration` capture session workflow.
It is not a full calibration solve yet. It creates capture sessions that later
target detection and mono/stereo solvers can consume.

## Commands

Dry-run mono session:

```bash
cd tools/calibration
uv run tennisbot-calibration capture mono \
  --camera-id cam1 \
  --device /dev/video0 \
  --output ../../artifacts/calibration_sessions/20260629_cam1_dry_run \
  --frame-count 3 \
  --interval-ms 0 \
  --width 320 \
  --height 180 \
  --dry-run
```

Dry-run stereo session:

```bash
cd tools/calibration
uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/20260629_stereo_dry_run \
  --pair-count 3 \
  --interval-ms 0 \
  --width 320 \
  --height 180 \
  --dry-run
```

Real stereo hardware probe:

```bash
cd tools/calibration
timeout 12s uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/20260629_stereo_hardware_probe \
  --pair-count 1 \
  --interval-ms 0 \
  --width 1280 \
  --height 720 \
  --fourcc MJPG \
  --fps 30
```

Quality-gated dry-run stereo session:

```bash
cd tools/calibration
uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/20260629_stereo_quality_dry_run \
  --pair-count 2 \
  --interval-ms 0 \
  --width 320 \
  --height 180 \
  --prepare-uvc-controls \
  --dry-run
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/20260629_stereo_quality_dry_run \
  --output-report ../../docs/calibration_capture_quality_20260629.md
```

Rendered ChArUco detection dry-run:

```bash
cd tools/calibration
uv run tennisbot-calibration capture mono \
  --camera-id cam1 \
  --output ../../artifacts/calibration_sessions/20260629_charuco_detection_dry_run \
  --frame-count 1 \
  --interval-ms 0 \
  --width 960 \
  --height 640 \
  --dry-run
# Replace the dry-run frame with a rendered DFOptix ChArUco board, then detect:
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/20260629_charuco_detection_dry_run \
  --output ../../artifacts/calibration_sessions/20260629_charuco_detection_dry_run/observations.json \
  --output-report ../../docs/calibration_charuco_detection_20260629.md
```

Quality-gated real stereo hardware probe:

```bash
cd tools/calibration
timeout 20s uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe \
  --pair-count 1 \
  --interval-ms 0 \
  --width 1280 \
  --height 720 \
  --fourcc MJPG \
  --fps 30 \
  --prepare-uvc-controls
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe \
  --output-report ../../docs/calibration_capture_quality_hardware_probe_20260629.md || true
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe \
  --output ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe/observations.json \
  --output-report ../../docs/calibration_charuco_detection_hardware_probe_20260629.md || true
```

## Result

```text
tools/calibration tests: 15 passed.
dry-run mono session: manifest.json, 3 PNG frames, summary.md, review.html.
dry-run stereo session: manifest.json, 3 left/right PNG pairs, summary.md, review.html.
hardware stereo probe: opened /dev/video0 and /dev/video2, wrote 1 left/right PNG pair at 1280x720 MJPG.
quality dry-run inspection: accepted=true, 4/4 images read, no issues.
quality hardware inspection: accepted=false, 2/2 images read, both frames rejected as low contrast / likely blank.
rendered ChArUco detection dry-run: accepted=true, 104 corners and 63 markers detected.
hardware ChArUco detection: accepted=false, 0/2 views accepted, 0/1 stereo pairs accepted.
```

The hardware probe proves this tool can open and save frames from the two local
USB cameras and can apply the same UVC brightness/gain/manual-exposure preset
used by the Live3D hardware verifier. The saved real frames are still uniform
gray and do not contain a visible calibration target, so they are not sufficient
for a mono or stereo solve.

## Remaining Work

- Capture real mono and stereo sessions with visible ChArUco targets that pass
  `capture inspect` and `capture detect-charuco`.
- Add mono calibration solving from accepted mono observations.
- Add stereo calibration solving from accepted stereo observations and mono
  intrinsics.
- Add a richer review GUI for accepting/rejecting captured frames before solve.
