# Headless Chassis Position Subscription Result

Date: 2026-07-03

## Summary

Changed `tennisbot_headless_vision` to consume the interface-layer chassis pose
topic:

```text
/robot/chassis_state
  -> chassis_position_publisher_node
  -> /robot/chassis_position target_msgs/ChassisPosition
  -> tennisbot_headless_vision
```

The target output chain is unchanged:

```text
tennisbot_headless_vision
  -> /target/raw target_msgs/RawTarget
  -> target_manager
  -> /target/managed target_msgs/ManagedTarget
```

## Changes

- Replaced the headless vision subscription from
  `std_msgs/Float64MultiArray /robot/chassis_state` to
  `target_msgs/ChassisPosition /robot/chassis_position`.
- Use `ChassisPosition.publish_stamp` as the internal pose sample timestamp.
- Renamed runtime parameters to:
  - `chassis_position_topic`
  - `chassis_position_input_frame`
- Removed the direct `std_msgs` runtime dependency from
  `tennisbot_headless_vision`.
- Updated current run docs and topic diagnostics to inspect
  `/robot/chassis_position`.

## Verification

Commands run:

```bash
git diff --check
python3 -m compileall -q src/tennisbot_headless_vision
PYTHONPATH=src/tennisbot_headless_vision python3 -m unittest discover -s src/tennisbot_headless_vision/tests -v
bun scripts/headless.ts --help
```

Results:

- `git diff --check`: passed.
- Python compileall: passed.
- Python trajectory unittest: 4 tests passed.
- Bun headless CLI help: passed.

Full ROS launch and topic validation still needs the target machine or sourced
control workspace that provides `target_msgs/ChassisPosition` and
`target_manager`.
