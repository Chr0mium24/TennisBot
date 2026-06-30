# Legacy Calibration GUI Replacement Result

Date: 2026-07-01

## Summary

Migrated the legacy CameraCalibLab ChArUco auto-capture GUI behavior into
`tools/calibration` without runtime imports from local legacy directories.

The implementation is split by responsibility:

- `capture_types.py`: config, camera, path, and JSON primitives.
- `charuco_detection.py`: ChArUco board creation and detection.
- `capture_quality.py`: full-corner, exposure, sharpness, stability, bucket,
  and dwell gates.
- `capture_overlay.py`: OpenCV overlays, bucket grid, status text, and
  Calibrate button.
- `capture_artifacts.py`: `session.json`, `manifest.json`, metadata, summaries,
  and saved image records.
- `capture_gui.py`: mono and stereo GUI loops only.

## Solver Format Decision

The solver now treats migrated `session.json` files as the only capture session
format for `--session` input. It no longer parses the simplified manifest-only
capture shape.

Stereo session loading pairs frames by `side=left/right`; runtime export IDs
still come from solve arguments such as `cam1` and `cam2`.

## Verification

```bash
cd tools/calibration
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

- `9 passed in 0.45s`
