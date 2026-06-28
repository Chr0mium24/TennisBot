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

Lead review tightened local artifact serving to resolve real paths, require
served targets to be files, and reject symlink escapes. Artifact status text is
HTML-escaped before rendering.

## Verification

```text
cd apps/live3d
bun test
bun run typecheck
bun run build
```

All checks passed before commit.

After merge, the lead generated dry-run YOLO and stereo calibration artifacts
with `tools/yolo` and `tools/calibration`, started the Live3D server, and
confirmed:

- `/artifacts/models/tennis_ball_yolo/package.json` served the YOLO package;
- `/artifacts/calibration/stereo_cam1_cam2/package.json` served the calibration
  package;
- `/artifacts/../README.md` returned `404`.

## Scope Notes

- Edited only `apps/live3d/**` and `docs/**`.
- Did not edit `packages/**`, `tools/**`, lab subtrees, or `.gitmodules`.
- Did not generate or retain smoke artifacts under `artifacts/**`.
