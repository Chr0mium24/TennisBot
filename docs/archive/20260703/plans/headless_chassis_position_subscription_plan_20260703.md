# Headless Chassis Position Subscription Plan

Date: 2026-07-03

## Goal

Align the headless vision runtime with the interface layer chassis pose input by
subscribing to `target_msgs/ChassisPosition` on `/robot/chassis_position`
instead of reading `std_msgs/Float64MultiArray` directly from
`/robot/chassis_state`.

## Scope

1. Update `tennisbot_headless_vision` to import and subscribe to
   `target_msgs/ChassisPosition`.
2. Use `ChassisPosition.publish_stamp` as the pose sample timestamp.
3. Preserve the existing field/cartesian frame conversion parameter behavior,
   renamed for the new chassis position input.
4. Update default ROS parameters, runtime log metadata, and operator docs.
5. Run syntax and lightweight tests that do not require a sourced ROS
   `target_msgs` environment.

## Out Of Scope

- Do not change `RawTarget` or `ManagedTarget`.
- Do not add any local non-ROS catch-loop substitute.
- Do not validate a real catch loop without ROS/Gazebo or real chassis backend.
