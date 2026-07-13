# Calibration pre-capture parameter reporting result

## Delivered

- Added `camera-calib-lab camera controls --devices <devices>`, which prints the current exposure mode/time, brightness, gain, white-balance mode/temperature, and focus mode/value before capture. Unsupported controls are labelled explicitly.
- `scripts/calib.py mono <camera>` now runs that report before it opens the mono capture GUI.
- `scripts/calib.py stereo` resolves and prints the cam1/cam2 mono packages before capture, then prints both cameras' controls before it opens the stereo capture GUI.
- Expanded the persisted calibration control snapshot to include white-balance and focus controls when available.

## Verification

- `cd tools/calibration && uv run pytest`: 23 passed.
- `uv run scripts/calib.py mono cam1 --dry-run`: reports the controls step before the capture step.
- `uv run scripts/calib.py stereo --dry-run`: prints selected mono package paths, then the controls step, then the capture step.
- `uv run --project tools/calibration camera-calib-lab camera controls --devices /dev/video0,/dev/video2`: command completed and reported unsupported controls for the current environment, which has no accessible V4L2 cameras.

## Note

Running `uv run --project tools/calibration pytest` from the repository root collected unrelated workspace tests and failed during dependency collection. The project-local command above uses the calibration project's `testpaths = ["tests"]` configuration and passed.
