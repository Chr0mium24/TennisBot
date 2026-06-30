# Calibration Pytest ROS Plugin Isolation Result

## Summary

`tools/calibration` now has a project-local pytest entry point that sets
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` before importing pytest. This prevents
system ROS pytest plugins from being auto-loaded when ROS environment variables
put `/opt/ros/humble` on Python's import path.

The project also declares pytest in the `dev` dependency group and keeps local
pytest configuration in `pyproject.toml`.

## Direct Install Check

Installing only `lark` is not sufficient in this environment:

- `uv run --with pytest --with lark python -m pytest -q`
- Result: advanced past `ModuleNotFoundError: No module named 'lark'`, then
  failed because ROS `launch_testing` is incompatible with pytest 9 hooks.

Installing both an older pytest and `lark` does run:

- `uv run --with 'pytest==7.4.4' --with lark python -m pytest -q`
- Result: `9 passed in 0.38s`

That route keeps non-ROS calibration tests coupled to the system ROS pytest
plugin set, so it was not used as the project default.

## Verification

After reinstalling the editable package so `.venv/bin/pytest` points at the
project wrapper:

```bash
uv sync --reinstall-package tennisbot-calibration
uv run pytest -q
```

Result:

```text
9 passed in 0.46s
```
