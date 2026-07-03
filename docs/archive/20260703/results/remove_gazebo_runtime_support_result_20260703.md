# Remove Gazebo Runtime Support Result

Date: 2026-07-03

## Summary

The current vision runtime surface now targets the real chassis/runtime chain
only. Gazebo and simulated-time launch support were removed from active code and
current operator documentation.

## Changes

- Removed the `--use-sim-time` option from `scripts/headless.ts`.
- Stopped passing `use_sim_time` to `tennisbot_headless_vision` and external
  `target_manager` launches.
- Removed the `use_sim_time` launch argument from
  `src/tennisbot_headless_vision/launch/headless_vision.launch.py`.
- Updated current docs to describe validation against the real chassis pose and
  control links only.
- Kept historical archive documents unchanged.

## Verification

```bash
rg -n "useSimTime|use-sim-time|use_sim_time|sim_time|Gazebo|gazebo|/clock" scripts src docs/current
bun scripts/headless.ts --help
uv run python -m compileall -q src/tennisbot_headless_vision
PYTHONPATH=src/tennisbot_headless_vision uv run python -m unittest discover -s src/tennisbot_headless_vision/tests -v
bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
bun scripts/headless.ts run --use-sim-time
```

Results:

- Active source/current docs search returned no Gazebo or simulated-time runtime
  support references.
- Launcher help no longer lists `--use-sim-time`.
- Python compile succeeded.
- Unit tests passed: 5 tests.
- Dry-run command contains no `use_sim_time` parameter.
- `--use-sim-time` now fails as an unknown option, as intended.
