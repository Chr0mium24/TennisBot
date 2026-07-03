# Rename Headless To Vision Runtime Result

Date: 2026-07-03

## Summary

Active runtime naming has been moved from `headless` to `vision runtime`.

## Changes

- Renamed ROS package path and package name:
  `src/tennisbot_headless_vision` -> `src/tennisbot_vision_runtime`.
- Renamed Python package:
  `tennisbot_headless_vision` -> `tennisbot_vision_runtime`.
- Renamed runtime executable and module:
  `headless_vision_node` -> `vision_runtime_node`.
- Renamed launch/config files:
  `headless_vision.launch.py` -> `vision_runtime.launch.py`,
  `headless_vision.yaml` -> `vision_runtime.yaml`.
- Renamed Bun launcher:
  `scripts/headless.ts` -> `scripts/vision-runtime.ts`.
- Updated README, current docs, and active tool docs to use the new naming.

Historical archive documents were not rewritten.

## Verification

```bash
rg -n "headless|Headless|HEADLESS|tennisbot_headless_vision|headless_vision|headless\\.ts|headless_ros" README.md docs/README.md docs/current scripts src/tennisbot_vision_runtime tools
bun scripts/vision-runtime.ts --help
bun scripts/vision-runtime.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
uv run python -m compileall -q src/tennisbot_vision_runtime
PYTHONPATH=src/tennisbot_vision_runtime uv run python -m unittest discover -s src/tennisbot_vision_runtime/tests -v
source /opt/ros/humble/setup.bash && colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
```

Results:

- Active source/current docs/tools search returned no remaining old headless
  identifiers.
- Launcher help uses `scripts/vision-runtime.ts`.
- Dry-run launches `ros2 run tennisbot_vision_runtime vision_runtime_node`.
- Python compile succeeded.
- Unit tests passed: 5 tests.
- ROS package build passed with the new package name.

Note: sourcing `/home/cr/tennis_robot_ws/install/setup.bash` was not possible on
this machine because that external workspace path does not exist here. The ROS
package build itself passed after sourcing `/opt/ros/humble/setup.bash`.
