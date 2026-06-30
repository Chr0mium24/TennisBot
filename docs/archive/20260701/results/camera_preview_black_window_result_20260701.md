# Camera Preview Black Window Result

Date: 2026-07-01

## Summary

Fixed the camera preview black-window path for `/dev/videoN` devices.

Root causes found during local hardware probes:

- A previous preview process could remain alive after terminal interruption and
  keep `/dev/video0` busy.
- The OpenCV path using `VideoCapture('/dev/video0')` did not return a frame
  during the probe, while `VideoCapture(0, cv2.CAP_V4L2)` returned a valid
  `1280x720` frame.
- The preview default preserved the current manual exposure and gain. On this
  camera that was `exposure_time_absolute=166`, `gain=32`, `brightness=-5`,
  which produced an ffmpeg brightness sample of only `3.0 / 255`.

## Changes

- Parse `/dev/videoN` as numeric V4L2 index `N` inside `OpenCVCamera`.
- Open numeric camera devices with `cv2.CAP_V4L2`.
- Set OpenCV FourCC before width, height, and FPS negotiation.
- Start preview in a high-visibility manual preset by default:
  `shutter=max`, `gain=max`, `brightness=max`.
- Add a `brightness` trackbar and `--brightness` preview option.
- Forward `SIGINT` and `SIGTERM` from `scripts/calib.ts` to the spawned
  `uv run camera-calib-lab ...` process, with a short forced-kill fallback.

## Verification

Passed:

```bash
cd tools/calibration && uv run python -m unittest discover -s tests
bun scripts/calib.ts preview cam1 --dry-run
cd tools/calibration && uv run camera-calib-lab camera preview --dry-run --device /dev/video0
cd tools/calibration && timeout 8s uv run python -u - <<'PY'
import cv2
import numpy as np
from camera_calib_lab.capture_gui import CameraConfig, OpenCVCamera
camera = OpenCVCamera('/dev/video0', CameraConfig(width_px=1280, height_px=720, fps=30.0, fourcc='MJPG'))
frame = camera.read()
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
print({'shape': frame.shape, 'mean': round(float(np.mean(gray)), 2), 'min': int(gray.min()), 'max': int(gray.max())})
camera.release()
PY
timeout 5s bun scripts/calib.ts preview cam1
fuser -v /dev/video0 /dev/video2 || true
git diff --check
```

Key observed results:

- Dry-run selected `shutter=2047`, `gain=255`, `brightness=64` for
  `/dev/video0` on this machine.
- The no-GUI `OpenCVCamera('/dev/video0')` probe returned a `720x1280` frame
  with mean luma `227.56`.
- The timed real-preview probe exited by timeout and left no process occupying
  `/dev/video0` or `/dev/video2`.

## Notes

The OpenCV Qt font warnings still print from the installed `opencv-python`
package, but they are unrelated to the black preview frame and did not block the
camera read path in the post-fix probe.
