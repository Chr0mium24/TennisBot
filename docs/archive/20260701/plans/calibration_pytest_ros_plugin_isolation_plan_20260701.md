# Calibration Pytest ROS Plugin Isolation Plan

## Problem

Running calibration tests with an ad-hoc pytest install can auto-load ROS
pytest plugins from `/opt/ros/humble`. In this environment, the ROS launch
plugin imports `lark`, which is not present in the active Python environment,
so pytest exits before collecting project tests.

`tools/calibration` also does not currently declare a pytest development
dependency, so `uv run pytest` has no project-local pytest executable.

## Plan

1. Add a project-local `pytest` console entry point for `tools/calibration`.
2. Set `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` before importing pytest in that entry
   point.
3. Declare pytest as a calibration dev dependency and add local pytest settings
   for `tests` and `src`.
4. Regenerate `tools/calibration/uv.lock` with `uv`.
5. Verify `uv run pytest -q` no longer imports ROS pytest plugins.
