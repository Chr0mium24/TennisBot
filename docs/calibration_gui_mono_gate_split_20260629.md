# Calibration GUI Mono Gate Split

Date: 2026-06-29

## Change

The Calibration GUI workflow sidebar now reports mono calibration packages as
separate gates:

- `Cam1 Mono`
- `Cam2 Mono`

Each gate selects the latest loaded mono package with the matching `camera_id`
instead of showing a single generic mono package. This matches the real
physical validation sequence, where cam1 mono and cam2 mono must both pass
before the stereo gate can be accepted.

## Verification

```text
tools/calibration/frontend/review bun test: 22 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
```
