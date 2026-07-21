# Headless ROS Runtime And Live3D Removal Result

Date: 2026-07-03

## Summary

- Removed the active Live3D application and root launcher from the tracked
  runtime path.
- Added `tennisbot_vision_msgs/msg/ChassisPose` for timestamped chassis pose.
- Extended `tennisbot_interface_adapter` to publish `/vision/chassis_pose` from
  `/robot/chassis_state` while preserving existing `/vision/chassis_position`
  and `/target/raw` forwarding.
- Added `tennisbot_headless_vision`, a ROS headless runtime package that reads
  real stereo camera frames, transforms ball observations into the
  field/interface frame, fits a gravity trajectory, and publishes
  `/vision/target_prediction`.
- Updated current docs, command references, and YOLO model-package consumer
  wording to point at the headless ROS runtime.

## Verification

Passed:

```bash
uv run -- python -m compileall -q src/tennisbot_headless_vision src/tennisbot_interface_adapter
```

Passed:

```bash
source /opt/ros/humble/setup.bash
PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/ros/humble/bin PYTHONNOUSERSITE=1 \
  colcon --log-base /tmp/tennisbot_headless_log build \
  --base-paths src \
  --build-base /tmp/tennisbot_headless_build \
  --install-base /tmp/tennisbot_headless_install \
  --packages-select target_msgs target_manager tennisbot_vision_msgs \
  tennisbot_interface_adapter tennisbot_headless_vision
```

Result:

```text
Summary: 5 packages finished
```

Passed:

```bash
source /opt/ros/humble/setup.bash
source /tmp/tennisbot_headless_install/setup.bash
ros2 interface show tennisbot_vision_msgs/msg/ChassisPose
ros2 interface show tennisbot_vision_msgs/msg/TargetPrediction
ros2 pkg executables tennisbot_headless_vision
ros2 pkg executables tennisbot_interface_adapter
ros2 launch tennisbot_headless_vision headless_vision.launch.py --show-args
ros2 launch tennisbot_interface_adapter interface_adapter.launch.py --show-args
```

Passed dry-run startup:

```bash
source /opt/ros/humble/setup.bash
source /tmp/tennisbot_headless_install/setup.bash
timeout 3 ros2 run tennisbot_headless_vision headless_vision_node \
  --ros-args -p dry_run:=true -p enable_camera:=false
```

The node initialized at 30 Hz and did not publish predictions while camera
runtime was disabled.

## Remaining Validation

- Measure the real mounted camera extrinsic and update
  `camera_translation_m`/`camera_rotation_rpy_rad`.
- Run with real stereo cameras, a real model package, and live
  `/vision/chassis_pose`.
- Verify `/vision/target_prediction` reaches `/target/raw` and
  `/target/managed` with consistent ROS clock timing.
- Complete real ROS/chassis or real chassis closed-loop validation before claiming
  real catch-loop completion.
