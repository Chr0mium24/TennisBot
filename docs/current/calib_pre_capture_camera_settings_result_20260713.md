# Calibration pre-capture camera settings result

## Delivered

The calibration wrapper now runs `camera prepare-calibration` before its parameter report and capture GUI for mono and stereo capture.

The preflight command applies the following V4L2 controls to every selected camera, in dependency-safe order:

1. `auto_exposure=1` and `exposure_time_absolute=10`
2. `white_balance_automatic=0` and `white_balance_temperature=4600`
3. `focus_automatic_continuous=0` and `focus_absolute=600`

The command fails before capture if a required control is unavailable or cannot be written. The following report command then reads back and prints the actual values.

## Verification

- `cd tools/calibration && uv run pytest`: 26 passed.
- Applied the preflight command to `/dev/video0,/dev/video2`, then read controls back. Both cameras reported manual exposure 10, manual white balance 4600 K, and manual focus 600.
