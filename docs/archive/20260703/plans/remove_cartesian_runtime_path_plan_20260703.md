# Remove Cartesian Runtime Path Plan

Date: 2026-07-03

## Goal

Make the headless vision runtime use the field/interface coordinate frame
directly, with no runtime Cartesian input mode or ROS-boundary conversion.

## Scope

1. Remove `chassis_position_input_frame` and the `cartesian` branch from
   `tennisbot_headless_vision`.
2. Treat `target_msgs/ChassisPosition.x/y/yaw` as already being in the
   field/interface frame.
3. Remove unused Cartesian pose conversion helpers from runtime geometry code.
4. Add a parity test proving the field-frame algorithm output matches a legacy
   Cartesian-frame calculation after coordinate conversion.
5. Update current docs so operators know the interface layer must publish
   field/interface coordinates.

## Non-Goals

- Do not change `RawTarget`, `ManagedTarget`, or target-manager behavior.
- Do not add a local catch-loop substitute.
- Do not claim real closed-loop validation without ROS/Gazebo or hardware.
