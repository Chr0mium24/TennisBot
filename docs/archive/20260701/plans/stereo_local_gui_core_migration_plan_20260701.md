# Local Stereo GUI Core Migration Plan

Date: 2026-07-01

## Goal

Migrate the useful stereo-coordinate behavior from the legacy local experiment
into tracked mainline code without depending on `desperate/`.

The target shape is:

- `packages/core`: shared TypeScript contracts and pure stereo geometry rules;
- `tools/stereo`: local Python/OpenCV 4K stereo YOLO GUI;
- `scripts/stereo.ts`: root launcher for the local stereo GUI.

## Scope

1. Keep rectification matrices and rectified detection centers in the shared
   contracts.
2. Extend `packages/core` with point rectification, calibration scaling,
   triangulation diagnostics, and calibration-aware pairing.
3. Add `tools/stereo` as a `uv` Python project that reads the current
   `artifacts/calibration/stereo_cam1_cam2` package and shows:
   x/y/z, range, disparity, epipolar error, reprojection error, and confidence.
4. Add `bun scripts/stereo.ts gui` as the root startup entry.
5. Update current docs and record validation results.

## Validation

Run:

```bash
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
cd tools/stereo && uv run pytest && uv run tennisbot-stereo gui --dry-run
bun scripts/stereo.ts --help
bun scripts/stereo.ts gui --dry-run
```
