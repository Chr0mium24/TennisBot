# Calibration Review GUI

Date: 2026-06-29

## Scope

`tools/calibration/frontend/review` is a standalone TypeScript/Bun review UI for
the local calibration workflow. It is isolated from the Python tool internals and
works with JSON artifacts produced by the CLI:

- capture `manifest.json`
- `inspection.json`
- ChArUco `observations.json`
- mono `package.json`
- stereo `package.json`
- package verification JSON

## Commands

```bash
cd tools/calibration/frontend/review
bun test
bun run build
PORT=5188 bun run dev
```

## Result

```text
bun test: 12 passed.
bun run build: main.js built under dist/assets; static index/styles copied.
```

The UI provides:

- workflow gate status for capture, inspection, ChArUco detection, mono solve,
  and stereo solve;
- JSON import by file picker or drag/drop;
- capture frame preview cards for local PNG frames referenced by
  `inspection.json` / `manifest.json` when the session path resolves under
  `/artifacts/...`;
- capture command builder for mono/stereo sessions;
- local whitelisted command execution for capture, inspect, detect, mono solve,
  stereo solve, and package verify through the Bun review server;
- automatic import of generated JSON artifacts returned by successful command
  runs, including `manifest.json`, `inspection.json`, `observations.json`,
  package `package.json`, and package verification JSON;
- inspection and ChArUco observation tables;
- mono/stereo solve command builder;
- mono/stereo package metric panels;
- a small Bun server that serves the UI and read-only files under
  `/artifacts/...` without allowing path traversal outside the artifacts root.

## Boundary

The GUI does not import `tennisbot_calibration` Python modules, YOLO tooling, or
legacy lab code. It consumes artifact-shaped JSON only.

## Remaining Work

- Add explicit accept/reject annotations for individual previewed frames.
- Add real hardware review screenshots after a visible ChArUco session is
  captured.
