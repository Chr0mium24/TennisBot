# Realtime Stereo HSV Detector - 2026-06-22

## Plan

Add a second realtime stereo GUI detector head so the same stereo calibration,
matching, and triangulation path can run with either:

- `--detector yolo`: current model-based tennis-ball detector.
- `--detector hsv`: fast yellow-green color threshold detector for center-region debugging and low-compute fallback.

## Implementation

- Added `HsvBallDetector` to `TennisBallDetectorLab`.
- Added CLI switch: `--detector yolo|hsv`.
- `--detector hsv` does not require `yolo/models/yolo/best.pt`.
- HSV detector parameters:
  - `--hsv-center-roi`: centered frame fraction to search, default `0.6`.
  - `--hsv-h-min`: default `22`.
  - `--hsv-h-max`: default `85`.
  - `--hsv-s-min`: default `70`.
  - `--hsv-v-min`: default `90`.
  - `--hsv-min-area`: default `12`.
  - `--hsv-max-area`: default `20000`.
  - `--hsv-morph-kernel`: default `5`.

## Tile Meaning

`--tile` is a YOLO-only mode. It splits a large frame into smaller crops, runs
YOLO on each crop, offsets detections back into full-frame coordinates, and
applies NMS. It is useful when a 4K frame contains a very small ball, but it is
slower than one full-frame inference.

## Run Commands

YOLO full-frame:

```bash
cd /home/cr/Codes/TennisBot/TennisBallDetectorLab
YOLO_CONFIG_DIR=/tmp/Ultralytics uv run tbl stereo-gui --detector yolo
```

YOLO tiled:

```bash
YOLO_CONFIG_DIR=/tmp/Ultralytics uv run tbl stereo-gui --detector yolo --tile
```

HSV center ROI:

```bash
uv run tbl stereo-gui --detector hsv --hsv-center-roi 0.6
```

## Verification

Commands:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall -q src tests
env UV_CACHE_DIR=/tmp/uv-cache PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl stereo-gui --help
```

Results:

- `compileall`: passed.
- `pytest`: `20 passed`.
- `tbl stereo-gui --help`: passed and lists `--detector`, HSV thresholds, and tile options.
