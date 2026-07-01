# Mono Capture Camera ID Fix Result

Date: 2026-07-01

## Changes

- Added `--camera-id` to `camera-calib-lab capture charuco-auto-gui`.
- `bun scripts/calib.ts mono cam1|cam2` now passes the camera id into the capture step.
- Mono capture applies the camera id before writing frame metadata, `session.json`, `manifest.json`, and `auto_gui_result.json`.
- Mono solve now rejects a requested `camera_id` when the session has no matching accepted views.

## Verification

Calibration tests:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

```text
19 passed in 0.51s
```

Dry run:

```bash
bun run scripts/calib.ts mono cam2 --dry-run
```

Confirmed the capture command includes:

```text
--device /dev/video2 --camera-id cam2
```
