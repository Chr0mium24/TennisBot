# Recording CLI migration result

## Delivered

- Migrated the local `~/Codes/record` workflow into `tools/recording`.
- Added `tennisbot-recording` uv CLI with:
  - `record single`
  - `record dual`
  - `gui single`
  - `extract-yolo-frames`
  - `normalize-timestamps`
  - `config show`
- Added the repository wrapper `uv run scripts/recording.py`.
- Saved current recording camera defaults in `tools/recording/configs/tennis_camera_recording.yaml`.
- Moved exposure, manual white balance, brightness, gain, sharpness, and related V4L2 controls out of shell-script defaults and into YAML config loading.
- Default recordings now write under ignored `runs/recording`.

## Verification

- `cd tools/recording && uv run pytest`: 7 passed.
- `uv run scripts/recording.py single --dry-run --duration 1 --exposure 123` printed the expected V4L2 setup and ffmpeg command, with `exposure_time_absolute=123` overriding the config.
- `uv run scripts/recording.py dual --dry-run --duration 1 --no-soft-sync` printed two camera setup commands and two ffmpeg capture commands for `/dev/video2` and `/dev/video0`.
- `uv run scripts/recording.py config show` printed the parsed YAML config from the repository root.
- `uv run scripts/recording.py extract --dry-run ...` mapped `video0` to `cam1` and `video2` to `cam2` without running ffmpeg.
- `uv run scripts/recording.py normalize --dry-run --base-epoch ...` printed the expected timestamp normalization ffmpeg commands.

## Not Verified

No real camera recording was run in this pass. The verification covered config parsing and command construction only.
