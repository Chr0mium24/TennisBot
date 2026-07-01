# Stereo Recording Replay Frontend Plan

Date: 2026-07-01

## Goal

Add a mainline recording and replay flow for `tools/stereo` without accepting
`--from/--to` CLI time-range arguments and without supporting legacy
`desperate` formats.

## Design

- `bun scripts/stereo.ts gui --record-run` records long stereo sessions from
  the existing OpenCV GUI.
- Each session is stored under `runs/stereo/<session>/` with:
  - `session.json` for metadata;
  - `points.ndjson` for matched 3D points;
  - `detections.ndjson` for per-frame detections and selected match metadata.
- `bun scripts/stereo.ts replay` starts a local TypeScript/Bun frontend.
- The frontend lists all session directories, loads the selected record, and
  uses two range sliders to select a time window.
- The frontend renders selected 3D points and a camera-frame prediction curve
  in the browser.

## Prediction Scope

The first replay prediction is camera-frame point prediction. It fits selected
3D points in their current left-camera coordinate frame and forecasts future
points. It does not claim a court/world landing point.

## Validation

Run:

```bash
cd tools/stereo && uv run pytest
cd tools/stereo && uv run python -m compileall src/tennisbot_stereo
cd tools/stereo/web/replay && bun test && bun run typecheck && bun run build
bun scripts/stereo.ts gui --dry-run --record-run
bun scripts/stereo.ts replay --help
```
