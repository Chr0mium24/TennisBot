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
bun test: 6 passed.
bun run build: main.js built under dist/assets; static index/styles copied.
```

The UI provides:

- workflow gate status for capture, inspection, ChArUco detection, mono solve,
  and stereo solve;
- JSON import by file picker or drag/drop;
- capture command builder for mono/stereo sessions;
- inspection and ChArUco observation tables;
- mono/stereo solve command builder;
- mono/stereo package metric panels;
- a small Bun server that serves the UI and read-only files under
  `/artifacts/...` without allowing path traversal outside the artifacts root.

## Boundary

The GUI does not import `tennisbot_calibration` Python modules, YOLO tooling, or
legacy lab code. It consumes artifact-shaped JSON only.

## Remaining Work

- Add direct browser previews for captured PNG frames.
- Add a backend bridge if the GUI should execute calibration commands instead of
  generating reviewed CLI commands.
- Add real hardware review screenshots after a visible ChArUco session is
  captured.
