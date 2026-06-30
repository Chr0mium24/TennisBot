# Camera Preview 4K30 Plan

Date: 2026-07-01

## Goal

Change the calibration camera preview default to `3840x2160` at `30 FPS`.

## Scope

- Update only the `camera preview` default capture size.
- Keep brightness checks at their existing sampling defaults.
- Keep calibration capture defaults and config-driven capture behavior unchanged.
- Preserve explicit `--width`, `--height`, and `--fps` overrides.

## Verification Plan

```bash
bun scripts/calib.ts preview cam1 --dry-run
cd tools/calibration && uv run camera-calib-lab camera preview --dry-run --device /dev/video0
cd tools/calibration && uv run python -m unittest discover -s tests
git diff --check
```

If the local UVC device is free, run a no-GUI `OpenCVCamera` probe at
`3840x2160 @ 30 FPS` to verify the negotiated frame size.
