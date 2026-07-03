# Remove Cartesian Runtime Path Result

Date: 2026-07-03

## Summary

Removed the runtime Cartesian input mode from `tennisbot_headless_vision`.
The headless runtime now treats `/robot/chassis_position` as the canonical
field/interface pose input:

```text
target_msgs/ChassisPosition
  publish_stamp
  sequence_id
  x       # field/interface x
  y       # field/interface y
  yaw     # field/interface yaw
```

There is no `chassis_position_input_frame` runtime parameter anymore. Cartesian
world-frame conversion, if needed by a chassis backend, must happen before
publishing `target_msgs/ChassisPosition`.

## Equivalence Proof Test

Added `test_coordinate_frame_parity.py`.

The test builds a fixed sample set of:

- camera-frame 3D points;
- matching chassis poses;
- a non-trivial camera-to-chassis transform.

It computes two paths:

1. Legacy path: transform observations and chassis pose in a standard Cartesian
   world frame, run trajectory prediction, then convert the output target to
   the field/interface frame.
2. Current path: convert the chassis pose first, run the camera-to-field
   transform and trajectory prediction directly in field/interface coordinates.

Assertions prove:

```text
field_target_x == legacy_cartesian_target_y
field_target_y == -legacy_cartesian_target_x
field_target_z == legacy_cartesian_target_z
field_t_remain == legacy_cartesian_t_remain
field_sigma_x == legacy_cartesian_sigma_y
field_sigma_y == legacy_cartesian_sigma_x
```

This demonstrates that the new direct field-frame algorithm is equivalent to
the old Cartesian-frame algorithm plus input/output coordinate conversion.

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
- Python unittest: 5 tests passed.
- Bun headless CLI help: passed.

Full ROS launch validation still requires a sourced ROS/control workspace with
`target_msgs` and the interface-layer publisher.
