# YOLO Runtime Main Chain ROI Tracking

Date: 2026-07-08

## Decision

主链路切到一个模型的两阶段运行策略：

1. 未锁定时跑 full-frame YOLO 搜索。
2. stereo matcher 选中有效左右检测后，左右相机各自以该检测中心锁定一个单 ROI。
3. 锁定后只在单 ROI 内跑 YOLO。
4. 连续若干帧没有有效 stereo match 后，回到 full-frame 搜索。

这不是双模型串联，也不是每帧 4 ROI 全扫。ROI 状态只由 stereo matcher 选中的左右检测更新，避免单目误检直接锁住主链路。

## Runtime Defaults

| item | value |
|---|---:|
| model | `artifacts/models/tennis_ball_yolo/model.pt` |
| promoted checkpoint | `final_trainpool_tiny_fixed_cp_imgsz960_batch32_20260708/weights/best.pt` |
| full-frame search imgsz | `1536` |
| ROI size | `1024x576` |
| ROI imgsz | `960` |
| expanded ROI | `1280x720` |
| lost after misses | `3` |
| conf | `0.05` |
| iou | `0.50` |

## Implementation

- `tools/stereo/src/tennisbot_stereo/detection.py`
  - added stereo-match-driven ROI tracking inside `YoloBallDetector`;
  - added `update_pair_tracks(match)` so the tracker updates after stereo matching;
  - added `tracking_status()` for runtime logs;
  - kept tiled inference mutually exclusive with ROI tracking.
- `src/tennisbot_vision_runtime/tennisbot_vision_runtime/vision_runtime_node.py`
  - added ROI/search parameters;
  - calls `update_pair_tracks(match)` after stereo matching;
  - writes ROI window/update metadata into the YOLO runtime log.
- `src/tennisbot_vision_runtime/config/vision_runtime.yaml`
  - enables ROI tracking by default for the main runtime.
- `tools/stereo/src/tennisbot_stereo/cli.py`
  - exposes the same ROI tracking knobs for local GUI debugging.
- `artifacts/models/tennis_ball_yolo`
  - regenerated the runtime package with the current best `.pt` checkpoint as
    the default model;
  - removed the old ONNX file from the package because the main Python runtime
    loads the `.pt` model and the old ONNX did not correspond to this checkpoint.

## Verification

- `uv run --project tools/stereo pytest tools/stereo/tests`: `7 passed`.
- `python3 -m compileall -q src/tennisbot_vision_runtime/tennisbot_vision_runtime tools/stereo/src/tennisbot_stereo`: passed.
- `git diff --check`: passed.
- `uv run --project tools/stereo tennisbot-stereo gui --dry-run --roi-tracking --search-imgsz 1536 --roi-imgsz 960 --roi-width 1024 --roi-height 576`: passed.
- `uv run --project tools/yolo python -m tennisbot_yolo.cli package verify --path artifacts/models/tennis_ball_yolo`: passed.

One broad `uv run --project tools/stereo pytest` invocation was intentionally
discarded because pytest rooted at the repository and collected legacy
`desperate/` tests outside the stereo tool environment.
