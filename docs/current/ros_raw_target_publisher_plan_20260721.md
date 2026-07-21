# ROS Raw Target Publisher Plan

## Goal

Keep the communication test surface minimal: one read command for the real
chassis-position input and one write command for a raw catching target.

## Changes

- Remove `communication publish-chassis-position`.
- Add `communication publish-raw-target` for `/target/raw`.
- Match the external `target_msgs/msg/RawTarget` fields and target-manager
  validation constraints observed on the ROS host.
- Preserve automatic ROS/control/local setup sourcing and dry-run support.
- Update unit tests and operator documentation.

## Validation

- Run the scoped vision Python test suite with `uv`.
- Run compile and diff checks.
- Verify CLI help and dry-run payload generation.
- Live ROS publication remains an on-host integration check with
  `target_manager` running.
