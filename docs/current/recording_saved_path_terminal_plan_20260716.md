# Recording Saved Path Terminal Plan

Date: 2026-07-16

## Goal

Print each video path in the terminal after a `tennisbot-recording` CLI capture
finishes, so the operator does not need to recover the paths from the startup
log.

## Scope

- Cover single-camera and dual-camera CLI recording.
- Print only output files that exist when the capture process returns.
- Keep dry-run output and GUI behavior unchanged.
- Add focused unit tests and run the recording tool test suite with `uv`.

## Expected Output

```text
Saved video: /path/to/session/camera.mkv
```
