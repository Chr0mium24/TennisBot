# Headless ROS Vision Runtime Target

Date: 2026-07-03

## Status

This document describes the target runtime architecture and the first headless
ROS implementation path. The code path exists, but it still needs real camera
and ROS/Gazebo or chassis validation.

Already available:

- `packages/core` has tested stereo geometry and trajectory prediction modules.
- `tools/stereo` has tested OpenCV stereo detection, matching, triangulation,
  and local recording paths.
- `src/interface/target_msgs` defines the imported external ROS interface.
- `src/tennisbot_interface_adapter` bridges vision-side topics to the external
  interface topics.
- `src/tennisbot_vision_msgs/msg/ChassisPose` defines the vision-side full
  chassis pose input.
- `src/tennisbot_headless_vision` owns the first headless stereo camera,
  field-frame transform, trajectory fit, and `/vision/target_prediction`
  publishing path.

Not yet available:

- A checked runtime configuration for the fixed camera pose on the chassis.
- Real hardware or ROS/Gazebo validation that `/vision/target_prediction`
  reaches `/target/raw` and `/target/managed` with correct timing.

## Runtime Goal

The real runtime should be one headless algorithm path, not a browser frontend.
The active tree no longer contains the old Live3D frontend path.

Target high-level flow:

```text
stereo cameras
  -> headless vision ROS node
  -> /vision/target_prediction
  -> tennisbot_interface_adapter
  -> /target/raw
  -> target_manager
  -> /target/managed
  -> chassis planner / state machine
```

The vision node also consumes chassis pose:

```text
ROS/Gazebo/chassis backend
  -> chassis pose x, y, yaw, stamp
  -> headless vision ROS node pose buffer
```

## Required Changes

### 1. Replace Live3D as the Main Runtime Path

The real runtime does not depend on `apps/live3d`. The replacement is a
headless ROS node that can run unattended with cameras and ROS topics.

Current migration state:

1. Live3D code and launcher are removed from the active tree.
2. `tennisbot_headless_vision` provides the headless ROS main chain.
3. `tennisbot_interface_adapter` provides `/vision/chassis_pose` from chassis
   state and forwards `/vision/target_prediction` to `/target/raw`.
4. Hardware validation remains required before claiming the real catch loop is
   complete.

### 2. Add the Headless Vision Node

The headless node should own the real-time algorithm:

```text
read left/right camera frames
  -> record capture_stamp from ROS clock immediately
  -> run YOLO
  -> pair left/right detections
  -> rectify and triangulate to camera-frame P_camera
  -> transform P_camera to chassis frame with configured T_chassis_camera
  -> transform chassis-frame point to field/interface frame with timestamped chassis pose
  -> maintain field-frame ball point history
  -> reject outliers and fit projectile trajectory
  -> predict target-plane point and remaining time
  -> publish tennisbot_vision_msgs/TargetPrediction on /vision/target_prediction
```

The node should publish only the vision-side topic. The adapter owns conversion
to the imported external interface:

```text
/vision/target_prediction
  -> /target/raw
```

### 3. Add Complete Chassis Pose

Because the cameras are mounted on the chassis, `x` and `y` are insufficient.
The transform needs the chassis heading at the image capture time.

Minimum required pose:

```text
stamp
x
y
yaw
```

Preferred pose if available:

```text
stamp
x
y
z
roll
pitch
yaw
```

The vision node should keep a small time-indexed pose buffer and query the pose
closest to each frame's `capture_stamp`. If exact sync is unavailable, the
implementation must bound interpolation/extrapolation error and drop frames
when pose age exceeds a configured threshold.

### 4. Add Chassis-to-Camera Extrinsics

The camera rig pose relative to the chassis is fixed and should be configured,
not hard-coded.

Required configuration:

```text
T_chassis_camera
  translation_m: [x, y, z]
  rotation_rpy_rad: [roll, pitch, yaw]
```

The world/field transform is:

```text
P_field = T_field_chassis(t_capture) * T_chassis_camera * P_camera
```

The transform must be applied before trajectory fitting, not only before
publishing.

### 5. Use Field/Interface Coordinates Internally

The field/interface frame is the canonical algorithm frame.

Origin:

```text
tennis-court geometric center = (0, 0)
```

Axis mapping from a standard Cartesian world frame:

```text
field_x = cartesian_y
field_y = -cartesian_x
field_z = cartesian_z
```

Inverse mapping:

```text
cartesian_x = -field_y
cartesian_y = field_x
cartesian_z = field_z
```

If yaw comes from a standard Cartesian heading measured from `+x`,
counter-clockwise positive:

```text
field_yaw = cartesian_yaw - pi / 2
cartesian_yaw = field_yaw + pi / 2
```

The algorithm should convert observations into field/interface coordinates as
soon as camera points are transformed through chassis pose. Trajectory fitting,
quality checks, prediction, logging, and `/vision/target_prediction` should all
use the same field/interface frame.

Do not convert only at the `/target/raw` publish boundary. That would leave
intermediate state, diagnostics, and future decisions in a different frame from
the interface output.

### 6. Use ROS Clock for All Runtime Timestamps

All runtime timestamps must come from the same ROS clock.

For direct OpenCV or camera SDK capture:

```python
capture_stamp = node.get_clock().now().to_msg()
```

Take this timestamp immediately after the frame is acquired. Do not use
`time.time()` as the interface timestamp.

For ROS camera topics, use:

```text
sensor_msgs/Image.header.stamp
```

provided that all related nodes use the same `use_sim_time` setting.

Real hardware:

```text
use_sim_time = false
```

Gazebo or `/clock` based simulation:

```text
use_sim_time = true
```

The `RawTarget` time convention depends on this:

```text
landing_time = capture_stamp + predicted_t_remain
real_t_remain = landing_time - manager_update_time
```

If `capture_stamp` and `target_manager` use different clocks, the remaining
time will be wrong.

### 7. Publish the Raw Target Input

The headless vision node publishes:

```text
/vision/target_prediction
tennisbot_vision_msgs/TargetPrediction
```

Required fields:

```text
capture_stamp
task_id
sequence_id
target_x
target_y
predicted_t_remain
sigma_x
sigma_y
```

The adapter converts this to:

```text
/target/raw
target_msgs/RawTarget
```

The vision node should not publish `/target/raw` directly. Keeping the adapter
in the path isolates repository-owned vision topics from the imported external
interface.

### 8. Confirm Target Semantics

The imported interface carries `target_x` and `target_y` as the predicted ball
position when the ball reaches the configured target plane. The current
headless runtime default is ground landing:

```text
target_plane_z = 0.0
```

If the chassis planner later expects a racket/catch height instead, set
`target_plane_z` to that field-frame height.

The current `RawTarget` message does not carry full 3D trajectory samples. It
carries the target `x/y` and remaining time. The full 3D world/field trajectory
can exist internally for fitting, diagnostics, and future messages, but it is
not part of the current external interface.

## Final Data Flow

```text
left/right camera frames
  -> capture_stamp from ROS clock
  -> YOLO detections
  -> stereo pairing
  -> rectification and triangulation
  -> P_camera
  -> T_chassis_camera
  -> P_chassis
  -> timestamped T_field_chassis
  -> P_field
  -> field-frame trajectory buffer
  -> target-plane prediction
  -> /vision/target_prediction
  -> tennisbot_interface_adapter
  -> /target/raw
  -> target_manager
  -> /target/managed
  -> chassis planner / state machine
```

## Verification Plan

Module-level checks:

```bash
cd packages/core && bun test
cd tools/stereo && uv run pytest
```

ROS package checks:

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash
ros2 pkg list
ros2 topic list -t
ros2 interface show tennisbot_vision_msgs/msg/ChassisPose
ros2 interface show tennisbot_vision_msgs/msg/TargetPrediction
ros2 interface show target_msgs/msg/RawTarget
```

Runtime topic checks:

```bash
ros2 topic hz /vision/target_prediction
ros2 topic echo /vision/target_prediction
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

Real closed-loop validation must use ROS/Gazebo or real chassis pose and
control links. A frontend-only or local substitute run cannot be counted as
real catch-loop verification.

## Acceptance Criteria

- The headless node runs without a browser frontend.
- It consumes timestamped chassis pose with yaw.
- It reads stereo camera frames and assigns ROS-clock capture stamps.
- It transforms triangulated ball points into field/interface coordinates
  before trajectory fitting.
- It publishes `/vision/target_prediction` at the expected nominal rate, up to
  30 Hz when data is available.
- The adapter forwards to `/target/raw`.
- `target_manager` produces `/target/managed` at no more than 10 Hz.
- The published target uses the configured target-plane semantic.
- Logs and diagnostics are in the same field/interface frame as the published
  target.
