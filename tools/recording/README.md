# TennisBot Recording Capability

`tools/recording` owns the ffmpeg/V4L2 encoder, GUI, session schema, clean
shutdown, and packet timestamp export. Operators should use the focused root
entry:

```bash
uv run scripts/record.py mono cam1
uv run scripts/record.py mono cam2 --gui
uv run scripts/record.py stereo
uv run scripts/record.py stereo --gui
```

Camera identities, capture defaults, and controls come from the shared
`tennisbot_camera` configuration. Encoding-specific defaults remain in
`configs/tennis_camera_recording.yaml`.

Outputs default to `runs/recording`. Every session has `session.json` and
`frames.ndjson`; stereo also has `pairs.ndjson`. GUI and headless modes use the
same recording builders and metadata writers. Soft synchronization is a
software timestamp relationship, not hardware synchronization.

Dataset frame extraction and timestamp normalization remain internal legacy
modules pending a separate data/media tool decision and are not exposed by
`scripts/record.py`.
