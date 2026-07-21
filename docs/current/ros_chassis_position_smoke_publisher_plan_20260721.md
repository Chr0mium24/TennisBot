# ROS Chassis Position Smoke Publisher Plan

## Goal

Add an explicit test CLI command that publishes one
`target_msgs/msg/ChassisPosition` message to `/robot/chassis_position` for ROS
interface smoke testing.

## Scope

- Add `communication publish-chassis-position` under `scripts/test.py`.
- Accept field-frame `x`, `y`, and `yaw`, plus a sequence id and topic override.
- Populate `publish_stamp` from the current system time by default.
- Reuse the existing automatic ROS/control/local setup sourcing.
- Add dry-run and unit coverage without requiring ROS to be installed locally.
- Document that this synthetic input is not real ROS/Gazebo closed-loop validation.

## Validation

- Run the vision Python pytest suite through `uv`.
- Run CLI help and dry-run checks through the repository wrapper.
- Confirm the Git worktree contains only the intended committed changes.
