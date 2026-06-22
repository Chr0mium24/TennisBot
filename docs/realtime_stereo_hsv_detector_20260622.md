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
  - `--hsv-h-min`: default `25`.
  - `--hsv-h-max`: default `60`.
  - `--hsv-s-min`: default `45`.
  - `--hsv-v-min`: default `80`.
  - `--hsv-min-area`: default `12`.
  - `--hsv-max-area`: default `250000`.
  - `--hsv-morph-kernel`: default `3`.

## Sample Image Tuning

User sample: `/tmp/codex-clipboard-QqYhKn.png`, 741 x 411.

Approximate tennis-ball ROI HSV quantiles from the sample:

| channel | p5 | p25 | p50 | p75 | p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| H | 38 | 41 | 44 | 47 | 50 |
| S | 59 | 92 | 109 | 123 | 134 |
| V | 95 | 120 | 137 | 159 | 193 |

Default HSV was changed from the broader/stricter `H=22..85, S>=70, V>=90`
to `H=25..60, S>=45, V>=80`. This captures more of the gray-green shadowed
ball surface while excluding most skin and light-bar pixels in the centered ROI.
`--hsv-max-area` was raised to `250000` so a close tennis ball is not rejected
when running at 4K resolution.

With the tuned defaults, the sample image produces the top HSV detection:

- center: `(259.4, 244.2)` px
- box size: `96.0 x 96.0` px
- confidence: `1.000`

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

HSV sample-tuned explicit parameters:

```bash
uv run tbl stereo-gui --detector hsv --hsv-center-roi 0.6 \
  --hsv-h-min 25 --hsv-h-max 60 --hsv-s-min 45 --hsv-v-min 80 \
  --hsv-min-area 12 --hsv-max-area 250000 --hsv-morph-kernel 3
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
- `pytest`: `21 passed`.
- `tbl stereo-gui --help`: passed and lists `--detector`, HSV thresholds, and tile options.
