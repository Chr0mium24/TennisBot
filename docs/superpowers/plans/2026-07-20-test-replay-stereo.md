# Test Replay Stereo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `uv run scripts/test.py replay stereo` for offline dual-camera recording replay, then generate a YOLO annotated 75-85 frame video.

**Architecture:** Keep `scripts/test.py` as a thin wrapper. Add reusable offline replay logic under `packages/vision-python/src/tennisbot_vision/offline_replay.py` and wire it through `tennisbot_vision.cli`. Reuse existing detector, calibration, stereo matcher, and render UI code.

**Tech Stack:** Python, uv, OpenCV, Ultralytics YOLO through the existing `detect` extra, existing `tennisbot_vision` package APIs.

## Global Constraints

- Do not add local fake robot tracking or catch-loop substitute logic.
- This is offline recording diagnostics only; do not claim real ROS/chassis closed-loop validation.
- Save implementation plan and experimental result as Markdown.
- Commit all repo changes before completion.
- Use explicit calibration package paths; do not silently default to the old fixed runtime package.

---

### Task 1: Add replay parser coverage

**Files:**
- Modify: `packages/vision-python/tests/test_test_cli.py`
- Modify: `packages/vision-python/src/tennisbot_vision/cli.py`

**Interfaces:**
- Produces CLI command: `test.py replay stereo`
- Consumes `run_offline_stereo_replay(args)` from Task 2

- [ ] Add failing tests that `replay stereo --dry-run` accepts `--recording`, `--calibration-package`, `--frame-start`, `--frame-end`, `--stride`, `--sync`, and `--record-overlay`.
- [ ] Run targeted test and verify it fails because the replay command does not exist.
- [ ] Add parser wiring and dry-run payload.
- [ ] Run targeted test and verify it passes.

### Task 2: Add offline replay core

**Files:**
- Create: `packages/vision-python/src/tennisbot_vision/offline_replay.py`
- Modify: `packages/vision-python/tests/test_test_cli.py`

**Interfaces:**
- Produces `run_offline_stereo_replay(args) -> int`
- Resolves recording directory streams from `session.json` or `*_video0.mkv` / `*_video2.mkv`
- Supports `frame-index` and `pts` sync modes, with first implementation preserving frame-index generation and recording sync metadata

- [ ] Add unit tests for recording stream resolution and frame range validation.
- [ ] Implement stream resolution, frame range/stride validation, overlay writing, metrics writing, and summary writing.
- [ ] Reuse `YoloBallDetector`, `RuntimeStereoCalibration`, `StereoBallMatcher`, and `render_gui`.
- [ ] Run package tests.

### Task 3: Generate requested replay artifact

**Files:**
- Create: `docs/current/test_replay_stereo_75_85_result_20260720.md`
- Output runtime files under: `runs/test/replay_20260717_155414_75_85/`

**Interfaces:**
- Uses command:
  `uv run scripts/test.py replay stereo --recording runs/recording/20260717_155414 --calibration-package artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST --frame-start 75 --frame-end 85 --stride 1 --record-overlay`

- [ ] Run the replay command.
- [ ] Verify `overlay.mp4`, `summary.json`, and `metrics.ndjson` exist and are non-empty.
- [ ] Save a Markdown result with command, input, output, and key metrics.
- [ ] Commit implementation and result.
