# Camera Preview Black Window Plan

Date: 2026-07-01

## Problem

`bun run scripts/calib.ts preview cam1` opens an OpenCV window, but the visible
frame is black. `bun run scripts/calib.ts brightness` still reports numeric
brightness for the same camera path.

## Working Hypotheses

- The preview command switches the device to manual exposure while keeping a
  very short current exposure value, so frames become visually black even though
  the device can capture valid frames in the brightness check.
- The OpenCV preview path negotiates a different V4L2 format than the ffmpeg
  brightness path.
- The preview overlays are present, but the underlying camera frame mean luma is
  near zero and needs a clearer startup preset or diagnostics.

## Scope

- Keep the real camera preview path dependent on V4L2/OpenCV hardware capture.
- Do not add simulated camera frames or any replacement capture logic.
- Preserve the Bun wrapper and Python `uv` tool boundaries.

## Verification Plan

```bash
bun scripts/calib.ts preview cam1 --dry-run
cd tools/calibration && uv run camera-calib-lab camera preview --dry-run --device /dev/video0
cd tools/calibration && uv run python -m unittest discover -s tests
git diff --check
```

Hardware GUI preview may still require local operator confirmation because the
OpenCV window is interactive and blocks until `q` or `esc`.
