# ROS Raw Target Publisher Result

## Result

The communication test surface now has one read path and one write path:

```bash
uv run scripts/test.py communication chassis-position
uv run scripts/test.py communication publish-raw-target \
  --task-id 1 --sequence-id 0 --target-x 1.0 --target-y 2.0
```

The obsolete artificial `/robot/chassis_position` publisher was removed. The
write command now publishes one `target_msgs/msg/RawTarget` on `/target/raw`
with capture time, task/sequence identifiers, predicted remaining time, and
uncertainty fields matching the external control workspace.

Input validation mirrors the relevant `target_manager` constraints: uint64
task ids, uint32 sequence ids, positive remaining time up to five seconds, and
nonnegative uncertainty.

## Remote inspection

The ROS host at `nvidia3@172.21.51.52` confirmed the authoritative message
definitions under `~/tennis_robot_ws/src/interface/target_msgs/msg/` and the
manager implementation under `target_manager/target_manager_node.py`. At the
time of inspection, no business ROS nodes or target topics were active, so no
live target was injected.

## Validation

- Vision Python tests: `13 passed`.
- Python compile check: passed.
- CLI help: passed.
- Raw-target dry-run generated all authoritative message fields: passed.
- `git diff --check`: passed.

Live DDS delivery and `/target/managed` output require starting the external
`target_manager` on the ROS host.
