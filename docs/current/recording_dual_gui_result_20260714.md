# Recording dual GUI result

## Delivered

- Added `uv run scripts/recording.py gui dual`.
- Added a side-by-side dual-camera Tk preview in `tools/recording`.
- The dual GUI uses the same YAML-loaded V4L2 controls as the single recorder.
- Recording from the dual GUI stops preview, reapplies camera settings, writes `session.json`, and starts the existing parallel dual ffmpeg recording commands.
- Added `--devices`, `--preview-width`, `--preview-fps`, `--soft-sync`, `--no-soft-sync`, control overrides, and `--dry-run` to `gui dual`.
- Updated README and command usage docs.

## Verification

- `cd tools/recording && uv run pytest`: 8 passed.
- `uv run scripts/recording.py gui dual --dry-run` printed the default `/dev/video2,/dev/video0` dual GUI configuration.
- `uv run scripts/recording.py gui dual --dry-run --devices /dev/video4,/dev/video6 --no-soft-sync` printed the requested device override and disabled soft sync.

## Not Verified

No real dual-camera GUI session was opened in this pass. The verification covered CLI behavior and command/config wiring.
