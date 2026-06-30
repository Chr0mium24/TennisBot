# Calib Wrapper Result

Date: 2026-06-30

## Summary

Added a project-level calibration wrapper at `scripts/calib.ts` so the common
camera and calibration flow can be run from the repository root:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

The wrapper keeps the current rig defaults:

- brightness devices: `/dev/video0,/dev/video2`
- `cam1`: `/dev/video0`
- `cam2`: `/dev/video2`
- stereo: left `/dev/video0`, right `/dev/video2`
- stereo package output: `artifacts/calibration/stereo_cam1_cam2`

It also supports `--dry-run`, `--capture-only`, `--solve-only`, device
overrides, session overrides, and output overrides.

## Verification

Passed:

```bash
bun scripts/calib.ts --help
bun scripts/calib.ts brightness --dry-run
bun scripts/calib.ts mono cam1 --dry-run
bun scripts/calib.ts mono cam2 --dry-run
bun scripts/calib.ts stereo --dry-run
bun scripts/live3d.ts --help
cd tools/calibration && uv run python -m unittest discover -s tests
git diff --check
```

The dry-run output confirmed that `brightness` now checks `/dev/video0` and
`/dev/video2` by default without frame capture and that mono/stereo commands
expand to the expected OpenCV capture and solve steps.

## Hardware Notes

No real calibration capture was run in this change. The GUI capture commands
were intentionally validated with `--dry-run` only.
