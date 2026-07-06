# Pose timestamp diagnostics result

## Context

Live runtime logs showed repeated `dropping frame without a recent chassis pose`
even after increasing `max_pose_age_s`. The existing event log did not include
the camera frame timestamp, closest chassis pose timestamp, or measured age.

## Change

When a stereo sample is dropped because no chassis pose is recent enough,
`events.ndjson` now records `dropped_frame_without_recent_pose` with:

- `frame_id`
- `capture_stamp`
- `capture_ns`
- `closest_pose_ns`
- `pose_delta_s` (`closest_pose_ns - capture_ns`)
- `pose_abs_age_s`
- `max_pose_age_s`
- `pose_buffer_size`

This makes it possible to distinguish missing chassis messages from timestamp
clock mismatch or excessive camera/YOLO latency.

## Verification

- `uv run -- python -m compileall -q src/tennisbot_vision_runtime`
  - Result: passed with no output.
- `PYTHONPATH=src/tennisbot_vision_runtime uv run python -m unittest discover -s src/tennisbot_vision_runtime/tests -v`
  - Result: 5 tests passed.
