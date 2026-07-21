# ROS Chassis Position Smoke Publisher Result

## Result

Added a single-message ROS interface smoke publisher:

```bash
uv run scripts/test.py communication publish-chassis-position \
  --x 1.0 --y -0.5 --yaw 0.25 --sequence-id 7
```

The command publishes `target_msgs/msg/ChassisPosition` once on
`/robot/chassis_position`. It uses the current system timestamp by default,
accepts field-frame `x/y/yaw`, and reuses the existing automatic setup sourcing.
Its output explicitly states that artificial pose publication is not real
ROS/Gazebo closed-loop validation.

## Validation

- `uv run --project packages/vision-python --extra test pytest -q packages/vision-python/tests`: `13 passed`.
- `uv run --project packages/vision-python python -m compileall -q packages/vision-python/src packages/vision-python/tests`: passed.
- CLI `--help`: passed.
- CLI `--dry-run --no-auto-source`: produced the expected `ros2 topic pub --once` command and field values.
- `git diff --check`: passed.

An initial repository-root pytest invocation collected unrelated independent uv
projects and failed import collection. Restricting pytest to the vision Python
package used the intended project boundary and passed. This macOS host does not
have ROS 2 installed, so live publication remains to be checked on the ROS host.
