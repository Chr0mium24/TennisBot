# Calibration GUI Current Artifacts Loader

Date: 2026-06-29

## Change

The Calibration GUI server now exposes a read-only current artifact endpoint:

```text
GET /api/calibration/current-artifacts
```

It loads the canonical local calibration artifacts from `artifacts/`:

- DFOptix ChArUco target metadata;
- target print-check JSON when it exists;
- cam1, cam2, and stereo default capture-session manifest, inspection, and
  observations JSON when they exist;
- cam1 and cam2 mono packages and verification JSON;
- stereo package and verification JSON.

The Calibration GUI now loads those current artifacts on startup, so the first
view can show the local target sheet links and package/session state without
manual JSON selection. The toolbar still has a `Load Current` button for manual
refresh. Repeated loads replace artifacts with the same path instead of
appending duplicates.

## Verification

```text
tools/calibration/frontend/review bun test: 18 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
GET http://127.0.0.1:5188/api/calibration/current-artifacts: returned schema tennisbot.calibration_current_artifacts.v1 and 7 artifacts.
bun scripts/start-local-runtime.ts --status: Live3D and Calibration GUI ready.
```

Follow-up default-session loader check:

```text
tools/calibration/frontend/review bun test: 20 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
```

Follow-up startup auto-load check:

```text
tools/calibration/frontend/review bun test: 21 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
```
