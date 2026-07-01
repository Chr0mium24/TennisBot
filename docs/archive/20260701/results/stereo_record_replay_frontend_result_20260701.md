# Stereo Recording Replay Frontend Result

Date: 2026-07-01

## Result

Implemented the mainline recording and replay flow for `tools/stereo`:

- `bun scripts/stereo.ts gui --tile --record-run` records long stereo runs under
  `runs/stereo/<session>/`;
- each recording writes `session.json`, `points.ndjson`, and
  `detections.ndjson`;
- `--record-preview-video` optionally writes `preview.mp4`;
- `bun scripts/stereo.ts replay` starts a local Bun/TypeScript replay frontend;
- the replay frontend lists session directories, loads a selected record, uses
  two UI sliders for the selected time range, and renders selected camera-frame
  points plus a prediction curve with Three.js.

The replay flow does not use `--from` or `--to` CLI arguments. Time-window
selection happens in the browser UI.

Prediction is camera-frame point prediction. It fits selected points in the
left-camera coordinate frame and does not claim a court/world landing point.

## Verification

Commands run:

```bash
cd tools/stereo && uv run pytest
cd tools/stereo && uv run python -m compileall src/tennisbot_stereo
cd tools/stereo/web/replay && bun test
cd tools/stereo/web/replay && bun run typecheck
cd tools/stereo/web/replay && bun run build
bun scripts/stereo.ts gui --dry-run --record-run
bun scripts/stereo.ts replay --help
bunx --bun playwright install chromium
git diff --check
```

Observed result:

- `tools/stereo`: 4 Python tests passed; compileall passed;
- `tools/stereo/web/replay`: 2 Bun tests passed; typecheck passed; browser
  bundle built successfully;
- root launcher dry-run printed `record_run=True` and `runs/stereo`;
- replay help confirms time-window selection is done in the browser UI.

A temporary replay server was started against a synthetic sample recording under
`/tmp/tennisbot-stereo-replay-sample`. Playwright Chromium screenshots passed at
`1280x800` and `390x844`, and a browser-level canvas check confirmed non-empty
WebGL pixels in both viewports. The server was stopped after verification.

No hardware camera recording session was opened during this change.
