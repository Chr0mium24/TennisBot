# Camera Preview Controls Result

Date: 2026-06-30

## Summary

Added a live camera preview/debug path before calibration:

```bash
bun scripts/calib.ts preview
bun scripts/calib.ts preview cam1
bun scripts/calib.ts preview cam2
```

The default preview opens `/dev/video0` and `/dev/video2`. Single-camera preview
uses `/dev/video0` for `cam1` and `/dev/video2` for `cam2`.

The OpenCV preview window provides trackbars for:

- `shutter`, mapped to UVC `exposure_time_absolute`
- `gain`, mapped to UVC `gain`

The tool uses `v4l2-ctl` to write camera controls. It switches to manual
exposure by default so shutter changes take effect. Use `q` or `esc` to close
the preview window.

## Verification

Passed:

```bash
uv run camera-calib-lab camera preview --help
uv run camera-calib-lab camera preview --dry-run
bun scripts/calib.ts --help
bun scripts/calib.ts preview --help
bun scripts/calib.ts preview --dry-run
bun scripts/calib.ts preview cam1 --dry-run
bun scripts/calib.ts preview cam2 --dry-run --shutter 400 --gain 64
bun scripts/live3d.ts --help
cd tools/calibration && uv run python -m unittest discover -s tests
git diff --check
```

The dry-run output confirmed that `/dev/video0` and `/dev/video2` expose
`exposure_time_absolute` and `gain` controls on this machine.

## Hardware Notes

No real preview GUI was opened during automated verification. The command was
validated with `--dry-run` to avoid blocking the terminal in an OpenCV window.
