# Recording Control Dependency Order Result

## Outcome

The recording plan now stores an ordered sequence of V4L2 control commands for
each camera instead of one combined `VIDIOC_S_EXT_CTRLS` request. GUI and
headless recording execute the same sequence:

1. `auto_exposure`, `white_balance_automatic`, and
   `focus_automatic_continuous`;
2. `exposure_time_absolute`, `white_balance_temperature`, and
   `focus_absolute`;
3. brightness, contrast, saturation, gamma, gain, power-line frequency,
   sharpness, and backlight compensation.

This ensures camera 2 completes `focus_automatic_continuous=0` before the
recorder writes `focus_absolute=0`, avoiding the observed inactive-control
`Input/output error` after camera reset or reconnection.

## Verification

- `cd tools/recording && uv run python -m pytest -q`: `12 passed`.
- Python compile check for recording source and tests: passed.
- Headless stereo dry-run: passed and printed three ordered control commands
  for each camera.
- Dual GUI dry-run: passed.

No physical V4L2 devices are available in this macOS workspace. Final hardware
acceptance should be run on the target host after reconnecting camera 2 so it
starts with continuous autofocus enabled; `uv run scripts/record.py stereo
--gui` should then configure both cameras without manual preparation.
