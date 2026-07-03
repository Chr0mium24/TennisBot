# Headless Bun Auto Source Result

Date: 2026-07-03

## Summary

`scripts/headless.ts` now auto-sources ROS setup files when it starts ROS child
processes. Operators can run the main chain from an unsourced terminal as long
as the default setup paths exist and the TennisBot ROS package has already been
built.

Default source chain:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
source /home/cr/Codes/TennisBot/install/setup.bash
```

Manual `ros2` CLI diagnostics still need the current terminal to be sourced,
because a child process cannot modify its parent shell environment.

## Controls

- `--no-auto-source` disables wrapping.
- `--clear-setup-files` clears the default source list.
- `--setup-file <path>` appends a setup file and can be repeated.
- `ROS_SETUP`, `TENNISBOT_CONTROL_SETUP`, and `TENNISBOT_LOCAL_SETUP` override
  the default setup paths.

## Verification

Passed:

```bash
bun --check scripts/headless.ts
bun scripts/headless.ts --help
bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
bun scripts/headless.ts run --dry-run --no-auto-source
git diff --check
```

Default dry-run now wraps both ROS child processes:

```text
bash -lc 'source /opt/ros/humble/setup.bash && source /home/cr/tennis_robot_ws/install/setup.bash && source /home/cr/Codes/TennisBot/install/setup.bash && exec ros2 launch target_manager target_manager.launch.py'
bash -lc 'source /opt/ros/humble/setup.bash && source /home/cr/tennis_robot_ws/install/setup.bash && source /home/cr/Codes/TennisBot/install/setup.bash && exec ros2 run tennisbot_headless_vision headless_vision_node --ros-args ...'
```

Opt-out dry-run still emits the raw ROS commands:

```text
ros2 launch target_manager target_manager.launch.py
ros2 run tennisbot_headless_vision headless_vision_node --ros-args ...
```
