# Local Stereo GUI Core Migration Result

Date: 2026-07-01

## Result

Implemented the local stereo-coordinate path without changing `apps/live3d`:

- extended `packages/contracts` for rectification matrices, rectified pair
  centers, and richer pairing diagnostics;
- extended `packages/core` with rectified point handling, image-size calibration
  scaling, signed rectified disparity, and calibration-aware stereo pairing;
- added `tools/stereo`, a `uv` Python/OpenCV project for the local 4K stereo
  YOLO coordinate GUI;
- added `bun scripts/stereo.ts gui` as the root launcher;
- updated current command, architecture, operator, status, and YOLO GUI docs.

The local GUI reads `artifacts/calibration/stereo_cam1_cam2`, opens
`/dev/video0,/dev/video2` at `3840x2160@30 MJPG` by default, and displays
left-camera-frame x/y/z/range plus disparity, epipolar, reprojection, and
confidence diagnostics.

## Verification

Commands run:

```bash
cd packages/contracts && bun test
cd packages/contracts && bun run typecheck
cd packages/core && bun test
cd packages/core && bun run typecheck
cd tools/stereo && uv run pytest
cd tools/stereo && uv run python -m compileall src/tennisbot_stereo
cd tools/stereo && uv run tennisbot-stereo gui --dry-run
cd tools/stereo && uv run tennisbot-stereo gui --help
bun scripts/stereo.ts --help
bun scripts/stereo.ts gui --dry-run
```

Observed result:

- contracts: 4 tests passed; typecheck passed;
- core: 26 tests passed; typecheck passed;
- tools/stereo: 3 tests passed; compileall passed;
- direct and root dry-run commands printed the expected 4K stereo defaults.

No hardware camera GUI session was opened during this change.
