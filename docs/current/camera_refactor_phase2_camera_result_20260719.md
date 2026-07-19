# Camera Refactor Phase 2 Camera Result

Date: 2026-07-19

## Implemented

- Added the shared `tennisbot-vision` uv project at
  `packages/vision-python`.
- Added canonical `cam1`/left `/dev/video0` and `cam2`/right `/dev/video2`
  identities, capture settings, and runtime/recording/test/calibration control
  profiles.
- Added reusable mono and sequential stereo frame sources with monotonic and
  Unix timestamps plus pair deltas.
- Added `scripts/camera.py` with `list`, `check`, `preview`, and `controls
  show/apply`.
- `check` reports read health, negotiated dimensions, mean frame brightness,
  and V4L2 control state. `preview` is deliberately raw and contains no model
  inference or recording.

## Verification

```text
uv run --project packages/vision-python --extra test pytest packages/vision-python/tests
1 passed

uv run scripts/camera.py --help
PASS

uv run scripts/camera.py list --json
PASS (no camera devices were attached in this environment)

uv run scripts/camera.py controls apply stereo --profile calibration --dry-run
PASS; commands resolved cam1 then cam2 and did not access hardware
```

Physical camera validation remains required on the target host.
