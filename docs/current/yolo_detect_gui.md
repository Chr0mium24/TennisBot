# YOLO Detect GUI Result

Date: 2026-06-29

## Implemented

- Added `tools/yolo/src/tennisbot_yolo/detect_gui.py`.
- Added CLI command `tennisbot-yolo detect-gui`.
- Added optional dependency extra `detect` for OpenCV, NumPy, and Ultralytics.
- Added CLI help and dry-run test coverage.
- Documented the 4K tiled detection command in `tools/yolo/README.md`.

## Usage

```bash
cd tools/yolo
uv run --extra detect tennisbot-yolo detect-gui \
  --devices /dev/video0,/dev/video2 \
  --width 3840 \
  --height 2160 \
  --fourcc MJPG \
  --model ../../artifacts/models/tennis_ball_yolo/model.pt \
  --tile \
  --imgsz 1280 \
  --display-width 720
```

The GUI is detection-only. It intentionally does not prove stereo geometry or
prediction correctness.

For stereo x/y/z display, use the local stereo GUI instead:

```bash
uv run scripts/stereo.py gui --tile
```

## Verification

```bash
cd tools/yolo
uv run --no-sync python -m tennisbot_yolo.cli detect-gui --help
uv run --no-sync python -m tennisbot_yolo.cli detect-gui --dry-run --devices /dev/video0,/dev/video2 --model ../../artifacts/models/tennis_ball_yolo/model.pt --tile
uv run --no-sync python -m compileall src/tennisbot_yolo
uv run --no-sync pytest -q
uv lock
```

Result: all commands completed successfully; `pytest` reported 14 passed.
