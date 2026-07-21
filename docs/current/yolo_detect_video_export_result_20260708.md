# YOLO Detect Video Export Result - 2026-07-08

## Summary

Implemented an offline YOLO video export command for existing video files:

```bash
uv run scripts/yolo.py detect-video input.mp4 \
  --output runs/yolo-detect/input_boxes.mp4 \
  --tile \
  --overwrite
```

The command writes an annotated mp4 with bounding boxes, center points,
confidence values, and a compact status overlay. It preserves source frame size
and FPS by default.

## Files Changed

- Added `tools/yolo/src/tennisbot_yolo/detect_video.py`.
- Registered `tennisbot-yolo detect-video` in the YOLO CLI.
- Exposed `uv run scripts/yolo.py detect-video`.
- Documented usage in `tools/yolo/README.md` and `docs/current/command_usage.md`.
- Added CLI help and dry-run test coverage.

## Important Boundary

This is offline 2D YOLO detection export only. It does not validate stereo
triangulation, trajectory prediction, ROS publication, simulator, or the real
catching closed loop. OpenCV export does not preserve audio.

The only video file found in the repo at implementation time,
`tools/yolo/workspace/dataset/record20260707/20260707_140849/20260707_140849_video0.mkv`,
was empty, so no real annotated video could be generated from existing repo
media.

## Verification

Passed:

```bash
uv run --project tools/yolo python -m tennisbot_yolo.cli detect-video --help
uv run --project tools/yolo python -m tennisbot_yolo.cli detect-video /tmp/input.mp4 --dry-run --output /tmp/input_boxes.mp4 --tile --imgsz 960 --stride 2
uv run scripts/yolo.py detect-video /tmp/input.mp4 --dry-run --output /tmp/input_boxes.mp4 --tile --imgsz 960 --stride 2
cd tools/yolo && uv run python -m tennisbot_yolo.cli detect-video /tmp/input.mp4 --dry-run --output /tmp/input_boxes.mp4 --tile --imgsz 960 --stride 2
cd tools/yolo && uv run python -m compileall src/tennisbot_yolo
cd tools/yolo && uv run pytest -q
```

`cd tools/yolo && uv run pytest -q` result: `47 passed`.

Observed non-blocking warning:

- `onnxruntime` printed a device-discovery warning for `/sys/class/drm/card0`
  during CLI startup. Commands still exited with code 0.

One intentionally corrected verification mistake:

- Running `uv run --project tools/yolo pytest -q` from the repo root collected
  unrelated legacy/root tests and failed on missing legacy dependencies. The
  correct command for this tool is `cd tools/yolo && uv run pytest -q`.
