# Headless Direct RawTarget Result

Date: 2026-07-03

## Summary

- Moved the main runtime target publisher into `tennisbot_headless_vision`.
- `tennisbot_headless_vision` now subscribes directly to `/robot/chassis_state`
  as `std_msgs/Float64MultiArray`.
- The node now publishes `target_msgs/RawTarget` directly on `/target/raw`.
- Field/cartesian chassis-state conversion now lives in the headless node via
  `chassis_state_input_frame`.
- The documented main startup path is now:

```text
/robot/chassis_state + stereo cameras
  -> tennisbot_headless_vision
  -> /target/raw
  -> target_manager
  -> /target/managed
```

The existing `tennisbot_interface_adapter` package remains in the tree as an
optional compatibility/debugging bridge, but it is no longer part of the
documented main runtime chain.

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
git diff --check -- README.md docs/current/architecture.md docs/current/chassis_pose_input_gap.md docs/current/command_usage.md docs/current/headless_ros_vision_runtime.md docs/current/operator_runbook.md docs/current/status.md docs/archive/20260703/plans/headless_direct_raw_target_plan_20260703.md src/tennisbot_headless_vision/config/headless_vision.yaml src/tennisbot_headless_vision/package.xml src/tennisbot_headless_vision/tennisbot_headless_vision/headless_vision_node.py
```

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

No `target_msgs` package was available from the currently sourced ROS
environment, so full ROS build and launch checks must be run on the machine or
shell where the TennisBot control workspace is installed and sourced.

## Follow-Up Validation

Run this in the intended ROS/control workspace shell:

```bash
source /opt/ros/humble/setup.bash
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select \
  target_manager tennisbot_headless_vision \
  --symlink-install --allow-overriding target_manager
source install/setup.bash
ros2 launch tennisbot_headless_vision headless_vision.launch.py --show-args
ros2 launch target_manager target_manager.launch.py --show-args
```

Runtime topic checks:

```bash
ros2 topic hz /robot/chassis_state
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```
