# External Target Manager Boundary Result

Date: 2026-07-03

## Summary

`target_manager` is treated as an external control-workspace package owned by
`/home/cr/tennis_robot_ws`, not by this TennisBot repository.

Changes made:

- Removed the duplicate local `src/interface/target_manager` package.
- Removed the stale local `src/interface/README.md`.
- Updated current operator docs so this repository only builds
  `tennisbot_headless_vision`.
- Kept `scripts/headless.ts` launching `ros2 launch target_manager
  target_manager.launch.py` by default, assuming the operator has sourced the
  external control workspace first.

## Runtime Boundary

```text
/home/cr/tennis_robot_ws
  target_msgs
  target_manager

TennisBot
  src/tennisbot_headless_vision
  scripts/headless.ts
```

The normal source/build order is now:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_headless_vision --symlink-install
source install/setup.bash
```

## Verification

Passed:

```bash
uv run -- python -m compileall -q src/tennisbot_headless_vision
PYTHONPATH=src/tennisbot_headless_vision uv run python -m unittest discover -s src/tennisbot_headless_vision/tests -v
bun scripts/headless.ts --help
bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
```

The unit test run executed 4 tests successfully.

The Bun dry-run produced the expected external manager launch plus the local
headless vision node launch:

```text
ros2 launch target_manager target_manager.launch.py
ros2 run tennisbot_headless_vision headless_vision_node --ros-args ...
```

Search check passed with no matches:

```bash
rg -n "src/interface|allow-overriding|packages-select[[:space:]]+target_manager|target_manager tennisbot_headless_vision|ROS interface packages|ROS interface 和 headless" README.md docs/current scripts src
```

## Blocked Check

Full `colcon build` validation was not run in this environment because
`/home/cr/tennis_robot_ws/install/setup.bash` is absent. The local
`tennisbot_headless_vision` package still correctly declares `target_msgs` as an
external ROS dependency, so the control workspace must be built and sourced
before building this repository's ROS package.
