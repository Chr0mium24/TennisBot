# Raw Stereo Record Entry Plan

Date: 2026-07-01

## Goal

Add a simple raw stereo video recorder entry:

```bash
bun scripts/stereo.ts record
```

The command should use the current stereo defaults and require no routine arguments.

## Behavior

- Default devices: `/dev/video0,/dev/video2`
- Default capture: `3840x2160@30 MJPG`
- Default output root: `runs/raw-stereo`
- Default duration: unlimited
- Stop keys: `q` or `esc` from the preview window
- Record raw full-resolution videos:
  - `left.mp4`
  - `right.mp4`
- Record timing metadata:
  - `session.json`
  - `frames.ndjson`
  - `pairs.ndjson`
- Show only a downsampled raw stereo preview while recording.
- Do not run YOLO, rectification, or overlay rendering in the record path.

## Verification

- Add unit coverage for raw recording metadata and `record --dry-run`.
- Run `tools/stereo` tests with `uv`.
- Update current command documentation.
