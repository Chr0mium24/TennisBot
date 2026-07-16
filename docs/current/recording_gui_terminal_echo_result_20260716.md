# Recording GUI Terminal Echo Result

Date: 2026-07-16

## Result

- Single-camera preview and recording ffmpeg processes no longer inherit the
  terminal stdin.
- Dual-camera preview and recording use the same non-interactive launcher.
- Existing stdout/stderr routing and GUI process termination behavior remain
  unchanged.
- CLI recording remains interactive where it needs terminal input.

## Verification

```bash
cd tools/recording
uv run pytest
```

Result: `10 passed in 0.05s`.

The regression test verifies that GUI subprocesses receive
`stdin=subprocess.DEVNULL`. No physical camera or interactive terminal GUI was
available for an end-to-end hardware reproduction.
