# Wave 7 Live3D Artifact Loader Results

Date: 2026-06-29

## Summary

- Added an app-local Live3D artifact adapter that reads YOLO and stereo
  calibration JSON through a small reader interface.
- Browser loading uses package roots under `/artifacts/...` and validates JSON
  with `packages/core` artifact helpers.
- Live3D now renders explicit loaded or blocked artifact status while keeping
  the rendered scene labelled as fixture-only.
- The local Live3D server maps `/artifacts/...` to the repo-root `artifacts/`
  directory without copying artifacts into `dist`.

## Verification

```text
cd apps/live3d
bun test
bun run typecheck
bun run build
```

All checks passed before commit.

## Scope Notes

- Edited only `apps/live3d/**` and `docs/**`.
- Did not edit `packages/**`, `tools/**`, lab subtrees, or `.gitmodules`.
- Did not generate or retain smoke artifacts under `artifacts/**`.
