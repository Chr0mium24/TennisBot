# Mono Capture Camera ID Fix Plan

Date: 2026-07-01

## Problem

`bun scripts/calib.ts mono cam2` passes `--camera-id cam2` only to the solve step. The capture step still uses the default `camera.camera_id` from the YAML config, so cam2 capture sessions can record `camera_id=cam1` while using `/dev/video2`.

## Fix

- Add a mono capture `--camera-id` option.
- Pass `cam1` or `cam2` from `scripts/calib.ts` into the capture command.
- Apply the camera id before writing mono frame metadata, `session.json`, and `manifest.json`.
- Tighten mono solve so a requested `camera_id` must match accepted views instead of silently using all views.

## Verification

- Add unit coverage for the capture config override.
- Add unit coverage for strict mono solve camera id matching.
- Run the calibration test suite with `uv`.
