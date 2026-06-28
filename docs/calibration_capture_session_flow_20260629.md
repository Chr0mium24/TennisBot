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
```

## Result

```text
tools/calibration tests: 15 passed.
dry-run mono session: manifest.json, 3 PNG frames, summary.md, review.html.
dry-run stereo session: manifest.json, 3 left/right PNG pairs, summary.md, review.html.
hardware stereo probe: opened /dev/video0 and /dev/video2, wrote 1 left/right PNG pair at 1280x720 MJPG.
quality dry-run inspection: accepted=true, 4/4 images read, no issues.
quality hardware inspection: accepted=false, 2/2 images read, both frames rejected as low contrast / likely blank.
```

The hardware probe proves this tool can open and save frames from the two local
USB cameras and can apply the same UVC brightness/gain/manual-exposure preset
used by the Live3D hardware verifier. The saved real frames are still uniform
gray and do not contain a visible calibration target, so they are not sufficient
for a mono or stereo solve.

## Remaining Work

- Add target detection for captured mono and stereo sessions.
- Add mono calibration solving from accepted mono sessions.
- Add stereo calibration solving from accepted stereo sessions and mono
  intrinsics.
- Add a richer review GUI for accepting/rejecting captured frames before solve.
