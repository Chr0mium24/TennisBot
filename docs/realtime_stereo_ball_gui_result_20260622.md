# Realtime Stereo Ball GUI Result - 2026-06-22

## Implementation

- Added `tbl stereo-gui` in `TennisBallDetectorLab`.
- Default detector model: `TennisBallDetectorLab/yolo/models/yolo/best.pt`.
- Default calibration inputs:
  - left mono: `CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7/calibration.json`
  - right mono: `CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_cam2/calibration.json`
  - stereo extrinsics: `CameraCalibLab/runs/calibrations/dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622/calibration.json`
- The GUI uses OpenCV windows and renders:
  - left/right camera frames with YOLO boxes;
  - selected stereo match;
  - `x/y/z` in meters relative to the left camera;
  - disparity, epipolar error, confidence, frame id, and FPS;
  - an X/Z position plot.

## Geometry Notes

- Coordinate convention: OpenCV left-camera frame, `x` right, `y` down, `z` forward.
- Camera matrices are scaled if live frame size differs from the calibration image size.
- The current stereo calibration produces `P2[0,3] = 78.99774150332722`, so the runtime automatically flips disparity sign and reports positive disparity for physically valid depth.
- Recovered baseline from current projection matrices: `0.05248616443700975 m`.

## Commands Verified

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall -q src tests
env UV_CACHE_DIR=/tmp/uv-cache PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl stereo-gui --help
env UV_CACHE_DIR=/tmp/uv-cache YOLO_CONFIG_DIR=/tmp/ultralytics uv run python - <<'PY'
from ultralytics import YOLO
YOLO("yolo/models/yolo/best.pt")
PY
```

## Results

- `compileall`: passed.
- `pytest`: `16 passed in 0.32s`.
- `tbl stereo-gui --help`: passed and showed the new camera/model/calibration options.
- YOLO model load: passed, task reported as `detect`.

## Run Command

```bash
cd /home/cr/Codes/TennisBot/TennisBallDetectorLab
YOLO_CONFIG_DIR=/tmp/Ultralytics uv run tbl stereo-gui \
  --left-device /dev/video0 \
  --right-device /dev/video1
```

For 4K small-ball detection:

```bash
YOLO_CONFIG_DIR=/tmp/Ultralytics uv run tbl stereo-gui --tile
```
