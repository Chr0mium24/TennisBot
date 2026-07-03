# Vision Runtime Wording Plan

Date: 2026-07-03

## Goal

Use `vision runtime` as the user-facing name for the camera-to-target runtime,
instead of emphasizing `headless` or `ROS` in prose.

## Scope

1. Rename the current runtime target document from the headless wording to
   `vision_runtime.md`.
2. Update current docs so prose says `vision runtime` / `视觉运行时`.
3. Update CLI help and runtime log labels to use `vision runtime`.
4. Keep compatibility identifiers for now:
   - `tennisbot_headless_vision`
   - `headless_vision.launch.py`
   - `scripts/headless.ts`
5. Update verification notes and create a result document.

## Non-Goals

- Do not rename the ROS package, executable, launch file, or Bun script path in
  this change.
- Do not change target topics or message contracts.
