# Headless Runtime Logging And Adapter Removal Result

Date: 2026-07-03

## Summary

- Removed the active `tennisbot_interface_adapter` ROS package.
- Removed the now-unused `tennisbot_vision_msgs` ROS message package.
- Moved stale root-level adapter/coordinate decision documents into
  `docs/archive/20260703/results/`.
- Added optional runtime logging to `tennisbot_headless_vision`.
- Added `scripts/headless.ts` for normal runtime launch, logged launch, and
  single-task launch with a caller-provided `task_id`.

Main runtime remains:

```text
/robot/chassis_state + stereo cameras
  -> tennisbot_headless_vision
  -> /target/raw
  -> target_manager
  -> /target/managed
```

## Runtime Logging

When enabled, the session directory is `runs/headless/<session>/`:

```text
session.json
left.mp4
right.mp4
frames.ndjson
chassis.ndjson
detections.ndjson
observations.ndjson
targets.ndjson
events.ndjson
```

Logged data:

- `frames.ndjson`: ROS capture timestamp and frame shape for each video frame.
- `chassis.ndjson`: raw `/robot/chassis_state` plus converted field pose.
- `detections.ndjson`: YOLO detections, selected stereo match, and diagnostics.
- `observations.ndjson`: selected camera-frame and field-frame ball points.
- `targets.ndjson`: published `RawTarget` messages.
- `events.ndjson`: runtime events and single-task completion events.

## Bun Entrypoints

Normal chain:

```bash
bun scripts/headless.ts run
```

Logged chain:

```bash
bun scripts/headless.ts run --record --session test01 --tile
```

Single task with a fixed `task_id`:

```bash
bun scripts/headless.ts task --task-id 42 --session catch42 --tile
```

`task` mode enables logging by default and sets:

```text
initial_task_id=42
single_task_mode=true
single_task_shutdown_on_complete=true
```

## Verification

Passed:

```bash
uv run -- python -m compileall -q src/tennisbot_headless_vision src/interface/target_manager
```

Passed:

```bash
PYTHONPATH=src/tennisbot_headless_vision uv run python -m unittest discover -s src/tennisbot_headless_vision/tests -v
```

Result:

```text
Ran 4 tests
OK
```

Passed:

```bash
bun scripts/headless.ts --help
bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
bun scripts/headless.ts task --task-id 42 --dry-run --session task42 --tile
```

Passed:

```bash
rg -n "tennisbot_interface_adapter|tennisbot_vision_msgs|/vision/chassis|/vision/target|TargetPrediction|ChassisPose|vision-side" README.md docs/current docs/README.md src scripts -g '!**/__pycache__/**'
```

The search returned no matches.

Blocked in this local environment:

```bash
source /opt/ros/humble/setup.bash
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select target_manager tennisbot_headless_vision --symlink-install --allow-overriding target_manager
```

Reason:

```text
/home/cr/tennis_robot_ws/install/setup.bash: No such file or directory
```

Full ROS build and launch validation still needs the intended control
workspace shell where `target_msgs` is installed and sourced.
