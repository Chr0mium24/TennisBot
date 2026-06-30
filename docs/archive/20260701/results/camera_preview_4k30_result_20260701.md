# Camera Preview 4K30 Result

Date: 2026-07-01

## Summary

Changed the calibration camera preview default from `1280x720 @ 30 FPS` to
`3840x2160 @ 30 FPS`.

This change only affects `camera-calib-lab camera preview` and the
`bun scripts/calib.ts preview ...` wrapper. Brightness checks and calibration
capture defaults remain unchanged.

## Verification

Passed:

```bash
bun scripts/calib.ts preview cam1 --dry-run
cd tools/calibration && uv run camera-calib-lab camera preview --dry-run --device /dev/video0
cd tools/calibration && uv run python -m unittest discover -s tests
bun scripts/calib.ts preview --help
v4l2-ctl -d /dev/video0 --set-ctrl=brightness=64,gain=255,auto_exposure=1,exposure_time_absolute=2047
cd tools/calibration && timeout 12s uv run python -u - <<'PY'
import cv2
import numpy as np
from camera_calib_lab.capture_gui import CameraConfig, OpenCVCamera
camera = OpenCVCamera('/dev/video0', CameraConfig(width_px=3840, height_px=2160, fps=30.0, fourcc='MJPG'))
frame = camera.read()
gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
print({'shape': frame.shape, 'mean': round(float(np.mean(gray)), 2), 'min': int(gray.min()), 'max': int(gray.max())})
camera.release()
PY
fuser -v /dev/video0 /dev/video2 || true
git diff --check
```

Key observed results:

- Dry-run reported `width=3840`, `height=2160`, `fps=30.0`, `fourcc=MJPG`.
- The no-GUI hardware probe returned `shape=(2160, 3840, 3)` with mean luma
  `214.5`.
- `/dev/video0` and `/dev/video2` were not left occupied after the probe.

## Notes

An unrelated in-progress legacy calibration GUI replacement change was present
in `tools/calibration/src/camera_calib_lab/capture_gui.py` during this work and
was intentionally not included in the 4K preview commit.
