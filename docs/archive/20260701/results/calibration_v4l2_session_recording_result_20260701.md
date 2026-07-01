# Calibration V4L2 Session Recording Result

Date: 2026-07-01

## Changes

- Added one shared V4L2 control module for parsing `v4l2-ctl --list-ctrls` output.
- ChArUco mono capture now records the current control snapshot under `camera.v4l2_controls` in `session.json`, `manifest.json`, and `auto_gui_result.json`.
- ChArUco stereo capture now records separate snapshots under `stereo_rig.left.v4l2_controls` and `stereo_rig.right.v4l2_controls`.
- The recorded controls are `auto_exposure`, `exposure_time_absolute`, `brightness`, and `gain` when reported by the device.
- Solver parsing remains unchanged because these values are capture metadata only.

## Verification

Command:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

```text
17 passed in 0.58s
```
