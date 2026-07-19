# Camera Refactor Phase 1 Inventory Result

Date: 2026-07-19

## Frozen identities and capture defaults

- `cam1` is the stereo left camera and currently resolves to `/dev/video0`.
- `cam2` is the stereo right camera and currently resolves to `/dev/video2`.
- The canonical capture default is `3840x2160 @ 30 fps`, MJPEG/MJPG.
- Device overrides remain available for deployment, but commands must express
  their business intent with `cam1`, `cam2`, or `stereo`.

This resolves the old conflict where `tools/recording` reversed `/dev/video0`
and `/dev/video2` relative to calibration and stereo diagnostics.

## Current owners and dependencies

| Capability | Current owner | Consumers |
| --- | --- | --- |
| camera controls | root script, calibration package, recording YAML | calibration, recording, stereo, ROS runtime |
| ffmpeg recording | `tools/recording` | recording CLI only |
| OpenCV stereo frame timestamps | `tools/stereo/raw_recording.py` | stereo record CLI/tests |
| calibration artifact loading | `tools/stereo/calibration.py` | stereo GUI, ROS runtime |
| YOLO and ROI inference | `tools/stereo/detection.py` | stereo GUI, ROS runtime |
| matching/triangulation | `tools/stereo/matching.py` | stereo GUI, ROS runtime |
| ROS communication check | `scripts/check-chassis-position.py` | direct operator entry only |

The ROS runtime currently inserts `tools/stereo/src` into `sys.path` and then
imports `tennisbot_stereo`. That dependency must be replaced before the legacy
tool is removed.

## Physical layout decision

Create `packages/vision-python` as the shared uv-managed Python distribution.
It owns:

- `tennisbot_camera`: identities, profiles, V4L2 inspection/application, frame
  sources, and preview;
- `tennisbot_vision`: calibration loading, YOLO inference, pairing,
  triangulation, diagnostic presentation, and attachable recording sinks.

The distribution is named `tennisbot-vision`. `tools/recording`, the new test
entry, and ROS runtime consume it as a package dependency. The ROS runtime no
longer accepts a source-tree path parameter and never mutates `sys.path`.

`tools/calibration` and `tools/recording` remain independent uv projects.
Their public root scripts orchestrate the frozen CLI contract. The root
scripts do not become owners of reusable algorithms.

## Session schema decision

All new recording sessions use `schema_version: 1`, stable camera IDs, a
session mode (`mono` or `stereo`), capture settings, control profile, start
time, and named stream paths in `session.json`. Stereo sessions additionally
carry `frames.ndjson` and `pairs.ndjson`; online test sessions add their
diagnostic NDJSON files and optional overlay paths.

The ffmpeg recorder remains the standalone recorder base. An in-process
OpenCV sink is used only when `test --record` attaches to already-open frames;
it must not reopen a V4L2 device.

## Deferred legacy utilities

Dataset frame extraction, timestamp normalization, and browser replay are not
part of `record` or `test`. Their source is retained under an internal legacy
module until a later media/data-tool decision, but their public root command
surfaces are removed in Phase 6.
