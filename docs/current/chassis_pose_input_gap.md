# Chassis Pose Input Contract

Date: 2026-07-03

## Problem

The vision runtime needs timestamped chassis pose to transform a
triangulated camera-frame ball point into the field/interface frame.

Minimum pose needed by the algorithm:

```text
stamp
x
y
yaw
```

Current behavior:

- `tennisbot_vision_runtime` subscribes to `/robot/chassis_position` as
  `target_msgs/ChassisPosition`;
- the internal pose sample timestamp comes from `ChassisPosition.publish_stamp`;
- if `x`, `y`, or `yaw` is non-finite, the vision runtime node drops the sample;
- without recent `/robot/chassis_position`, `tennisbot_vision_runtime` waits
  and does not publish `/target/raw`.

Expected `/robot/chassis_position` layout today:

```text
publish_stamp
sequence_id
x
y
yaw
```

The interface layer can still receive the lower-level
`/robot/chassis_state std_msgs/Float64MultiArray`
`[x_m, y_m, v_mps, phi_rad, yaw_rad, ground_speed_mps]`, but that array should
be converted by `chassis_position_publisher_node` before the vision runtime.

## Why Yaw Is Required

The stereo cameras are fixed on the chassis. A camera-frame 3D point is first
transformed into the chassis frame with configured camera extrinsics, then into
the field/interface frame with the chassis pose:

```text
P_field = T_field_chassis(t_capture) * T_chassis_camera * P_camera
```

`yaw` is part of `T_field_chassis`. If yaw is absent, the algorithm cannot know
which field direction the mounted cameras were facing when the image was
captured.

Using only chassis `x/y` is enough to translate the point, but not enough to
rotate it into the field frame. As soon as the chassis turns, world/field ball
coordinates and predicted ground landing point will be wrong.

## Coordinate Frame Boundary

The runtime algorithm is not Cartesian internally. It runs in the
field/interface frame.

Current boundary:

- `target_msgs/ChassisPosition` must already carry `x/y/yaw` in the
  field/interface frame;
- `tennisbot_vision_runtime` copies `/robot/chassis_position` into its
  internal pose buffer without Cartesian conversion;
- trajectory fitting, logging, and `/target/raw` publishing use
  field/interface coordinates.

## Relevant Files

- `src/tennisbot_vision_runtime/tennisbot_vision_runtime/vision_runtime_node.py`
  - reads `/robot/chassis_position`;
  - requires `x`, `y`, and `yaw`;
  - timestamps the internal pose sample from `publish_stamp`;
  - waits for recent chassis position;
  - publishes `/target/raw` only after real camera observation and recent pose
    are available.
- `src/tennisbot_vision_runtime/tennisbot_vision_runtime/geometry.py`
  - transforms camera/chassis points into field/interface coordinates.
- `src/tennisbot_vision_runtime/tennisbot_vision_runtime/trajectory.py`
  - fits the trajectory and predicts the configured target plane.

## Options

### Correct Fix

Make the interface layer publish yaw in `target_msgs/ChassisPosition` on
`/robot/chassis_position`.

This is required for accurate field/world coordinates when the camera rig is
mounted on a moving chassis.

### Temporary Fallback

Add an explicit fixed-yaw fallback such as:

```yaml
allow_missing_yaw: true
fallback_yaw_rad: 0.0
```

This should default to disabled. It is only acceptable when the chassis heading
is known to be fixed during the run. It should be treated as a diagnostic or
bring-up mode, not a correct closed-loop runtime.

This fallback is now implemented (2026-07-06). When `allow_missing_yaw=true`:
- The node opens cameras without waiting for `/robot/chassis_position`.
- Chassis position messages with non-finite yaw are accepted with
  `fallback_yaw_rad` replacing yaw.
- When no chassis pose is available in the buffer (empty or stale), a synthetic
  pose `(x=0, y=0, z=0, yaw=fallback_yaw_rad)` is used to transform camera
  points to field coordinates.

CLI usage:
```bash
bun scripts/vision-runtime.ts run --allow-missing-yaw --fallback-yaw 0.0
```

## Current Decision

Do not silently invent yaw.

The fallback mode is now implemented. When explicitly enabled via
`allow_missing_yaw:=true`, the node uses `fallback_yaw_rad` as a replacement.
This keeps the default behavior unchanged (missing yaw still blocks
`/target/raw`), while providing an opt-in diagnostic mode for debugging.
