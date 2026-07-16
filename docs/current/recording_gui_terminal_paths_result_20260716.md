# Recording GUI Terminal Paths Result

Date: 2026-07-16

## Result

- Single-camera GUI status now shows only recording state, elapsed time, and
  optional sampling rate.
- Dual-camera GUI status now shows only recording state and elapsed time.
- When recording stops, each existing output is printed to the launching
  terminal as `Saved video: <path>`.
- CLI and GUI now use the same saved-path reporting function.

## Verification

```bash
cd tools/recording
uv run pytest
```

Result: `11 passed in 0.06s`.

No physical camera was available for an end-to-end GUI recording, so the
existing output-path and process tests were used.
