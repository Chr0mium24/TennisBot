# YOLO Detect Video Export Plan - 2026-07-08

## Goal

Add an offline YOLO video export command that reads an existing video file and
writes an annotated video with detection boxes.

## Scope

- Add a `tennisbot-yolo detect-video` CLI command under `tools/yolo`.
- Reuse the current Ultralytics YOLO detector, confidence filtering, class
  filtering, and tiled inference support.
- Preserve the source video's frame size and FPS by default.
- Draw bounding boxes, center points, confidence labels, and a compact status
  overlay.
- Expose the command through `bun scripts/yolo.ts detect-video`.
- Document usage and add CLI dry-run/help coverage.

## Non-Goals

- Do not add ROS/Gazebo-independent catch-loop logic.
- Do not claim this validates the real stereo catching loop.
- Do not add local tracking, landing prediction, or robot substitute behavior.
- Do not preserve source-video audio; OpenCV video export is detection-only.

## Verification

- `uv run --project tools/yolo python -m tennisbot_yolo.cli detect-video --help`
- `uv run --project tools/yolo python -m tennisbot_yolo.cli detect-video --dry-run ...`
- `uv run --project tools/yolo pytest -q`
- `bun scripts/yolo.ts detect-video --dry-run ...`
