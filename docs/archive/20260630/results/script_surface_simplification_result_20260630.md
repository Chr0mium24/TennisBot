# Script Surface Simplification Result

Date: 2026-06-30

## Implemented

- Moved camera brightness checking into `tools/calibration`:
  `uv run camera-calib-lab camera brightness`.
- Added `tools/calibration/src/camera_calib_lab/brightness.py`.
- Replaced the root launcher with one Live3D-only script:
  `bun scripts/live3d.ts`.
- Removed root helper scripts:
  - `scripts/check-camera-brightness.ts`
  - `scripts/operator-preflight.ts`
  - `scripts/physical-validation-status.ts`
- Updated current docs and README to stop advertising removed root scripts.
- Kept archived historical reports intact.

## Verification

```bash
cd tools/calibration
uv run camera-calib-lab camera brightness --help
uv run python -m unittest discover -s tests

cd /home/cr/Codes/TennisBot
bun scripts/live3d.ts --help
bun scripts/live3d.ts --status

cd apps/live3d
bun test
bun run typecheck
bun run build
```

Result:

- Calibration brightness help: passed.
- Calibration tests: 3 passed.
- Live3D launcher help: passed.
- Live3D launcher status: ready at `http://127.0.0.1:5178/`.
- Live3D tests: 45 passed, 0 failed.
- Live3D typecheck: passed.
- Live3D build: passed.

## New Commands

```bash
bun scripts/live3d.ts
bun scripts/live3d.ts --status

cd tools/calibration
uv run camera-calib-lab camera brightness
uv run camera-calib-lab camera brightness --devices /dev/video0,/dev/video2
```
