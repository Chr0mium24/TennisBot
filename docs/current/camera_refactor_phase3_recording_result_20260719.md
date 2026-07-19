# Camera Refactor Phase 3 Recording Result

Date: 2026-07-19

## Implemented

- Added the focused `scripts/record.py` surface: mono `cam1`/`cam2` and stereo,
  headless by default with optional `--gui`.
- Recording now consumes canonical camera identities, capture settings, and
  the recording control profile from `tennisbot_camera`.
- Fixed stereo ordering to cam1 `/dev/video0` followed by cam2 `/dev/video2`.
- Mono and stereo write the same `tennisbot.recording.session.v1` session
  schema with stable camera IDs and named streams.
- After ffmpeg closes a video, ffprobe packet/frame timestamps are exported to
  `frames.ndjson`; stereo sessions also export indexed pairs, delta
  milliseconds, and a 10 ms threshold result to `pairs.ndjson`.
- GUI and headless recording share ffmpeg command builders, controls, session
  writers, timestamp exporters, and shutdown helpers.

The legacy extraction and timestamp-normalization implementation remains
internally available for audit, but it is not exposed by `record.py`.

## Verification

```text
uv run --project tools/recording pytest tools/recording/tests
12 passed

uv run scripts/record.py mono cam2 --dry-run --duration 1
PASS; resolved /dev/video2 and canonical controls

uv run scripts/record.py stereo --dry-run --duration 1
PASS; resolved /dev/video0 then /dev/video2

uv run scripts/record.py stereo --gui --dry-run
PASS; resolved the same devices, capture settings, soft sync, and controls
```

No cameras were available in the implementation environment, so encoder,
preview, and physical timestamp validation remain required on the target host.
