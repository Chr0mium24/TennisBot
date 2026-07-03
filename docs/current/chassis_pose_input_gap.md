# Chassis Pose Input Gap

Date: 2026-07-03

## Problem

The headless vision runtime needs timestamped chassis pose to transform a
triangulated camera-frame ball point into the field/interface frame.

Minimum pose needed by the algorithm:

```text
stamp
x
y
yaw
```

Current behavior:

- missing `stamp` is handled by `tennisbot_headless_vision`, which stamps the
  internal pose sample with the ROS clock when `/robot/chassis_state` is
  received;
- missing `yaw` is not solved;
- if `/robot/chassis_state` has fewer than five values, the headless node drops
  the sample;
- without recent `/robot/chassis_state`, `tennisbot_headless_vision` waits and
  does not publish `/target/raw`.

Expected `/robot/chassis_state` layout today:

```text
[x_m, y_m, v_mps, phi_rad, yaw_rad, ground_speed_mps]
```

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

Current conversion boundary:

- `tennisbot_headless_vision` converts `/robot/chassis_state` into its internal
  pose buffer;
- if `chassis_state_input_frame: cartesian`, the headless node applies:

```text
field_x = cartesian_y
field_y = -cartesian_x
field_yaw = cartesian_yaw - pi / 2
```

- if `chassis_state_input_frame: field`, the headless node assumes `x/y/yaw` are
  already in the field/interface frame;
- trajectory fitting and `/target/raw` publishing use field/interface
  coordinates.

## Relevant Files

- `src/tennisbot_headless_vision/tennisbot_headless_vision/headless_vision_node.py`
  - reads `/robot/chassis_state`;
  - currently requires `yaw_rad` at index `4`;
  - stamps the internal pose sample with ROS clock;
  - waits for recent chassis state;
  - publishes `/target/raw` only after real camera observation and recent pose
    are available.
- `src/tennisbot_headless_vision/tennisbot_headless_vision/geometry.py`
  - transforms camera/chassis points into field/interface coordinates.
- `src/tennisbot_headless_vision/tennisbot_headless_vision/trajectory.py`
  - fits the trajectory and predicts the configured target plane.

## Options

### Correct Fix

Make the chassis backend publish yaw in `/robot/chassis_state`.

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

## Current Decision

Do not silently invent yaw.

Until a fallback mode is explicitly added and enabled, missing yaw blocks
the internal pose buffer and therefore blocks `/target/raw`.
