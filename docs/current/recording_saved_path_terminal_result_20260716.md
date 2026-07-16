# Recording Saved Path Terminal Result

Date: 2026-07-16

## Result

- Single-camera CLI recording prints the saved video path after capture exits.
- Dual-camera CLI recording prints each existing saved video path after capture
  exits, including preview and parallel capture modes.
- Missing outputs are not reported as saved.
- Dry-run and recording GUI behavior are unchanged.

## Verification

Command:

```bash
cd tools/recording
uv run pytest
```

Result: `9 passed in 0.08s`.

No physical cameras were used, so this verifies path reporting logic and the
existing CLI behavior but not a live V4L2 recording session.
