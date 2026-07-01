# Raw Stereo Record Entry Result

Date: 2026-07-01

## Summary

Added a raw stereo video recording entry:

```bash
bun scripts/stereo.ts record
```

Default behavior:

- devices: `/dev/video0,/dev/video2`
- capture: `3840x2160@30 MJPG`
- output root: `runs/raw-stereo`
- duration: unlimited unless `--duration <seconds>` is provided
- stop key: `q` or `esc` in the preview window
- preview: downsampled raw left/right images only

The raw record path does not run YOLO, rectification, or overlay rendering. It
writes `left.mp4`, `right.mp4`, `session.json`, `frames.ndjson`, and
`pairs.ndjson`.

`bun scripts/stereo.ts preview` is now an alias for the existing coordinate GUI.
The old `gui --record-run` path remains the point/detection recorder under
`runs/stereo`.

## Verification

```bash
bun scripts/stereo.ts record --dry-run
```

Result:

```text
stereo_record=dry-run
devices=/dev/video0,/dev/video2
capture=3840x2160@30 fourcc=MJPG
duration=unlimited
preview_width=720
record_root=/home/cr/Codes/TennisBot/runs/raw-stereo
soft_sync_threshold_ms=25
```

```bash
cd tools/stereo && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Result:

```text
6 passed in 0.14s
```

Also verified:

```bash
cd tools/stereo && uv run tennisbot-stereo record --help
```
