# Recording Dual Stop Result

Date: 2026-07-16

## Result

- Dual recording now sends SIGINT to both ffmpeg processes before waiting.
- The graceful shutdown phase has one shared five-second timeout.
- Remaining processes are terminated together, then killed together only if
  still necessary.
- CLI `q`, CLI Ctrl+C, and dual GUI stop all use the corrected shutdown helper.

## Verification

```bash
cd tools/recording
uv run pytest
```

Result: `11 passed in 0.06s`.

The regression test confirms both capture processes receive SIGINT before the
first process wait begins. A physical dual-camera session was not available in
this environment.
