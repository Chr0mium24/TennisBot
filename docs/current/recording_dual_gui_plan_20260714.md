# Recording dual GUI plan

## Goal

Add `uv run scripts/recording.py gui dual` so recording operators can preview both cameras side by side, similar to the stereo recorder view, while still using the config-driven V4L2/ffmpeg recording path.

## Approach

1. Reuse `tools/recording` config loading and V4L2 controls.
2. Add a dual-camera Tk GUI that starts two ffmpeg preview pipes, decodes PPM frames, and displays them in left/right panes.
3. On recording start, stop preview, re-apply camera controls, build a dual ffmpeg recording plan, write `session.json`, and launch one ffmpeg process per camera.
4. On recording stop, interrupt both ffmpeg processes, restore preview, and show the saved output directory.
5. Add CLI and wrapper support for `gui dual`, plus dry-run and tests.

## Verification

- Unit-test CLI dry-run and dual GUI plan generation without opening cameras.
- Run `cd tools/recording && uv run pytest`.
- Run `uv run scripts/recording.py gui dual --dry-run`.
