# Calibration pre-capture parameter reporting result

## Delivered

- Added `camera-calib-lab camera controls --devices <devices>`, which prints the current exposure mode/time, brightness, gain, white-balance mode/temperature, and focus mode/value before capture. Unsupported controls are labelled explicitly.
- `scripts/calib.py mono <camera>` now runs that report before it opens the mono capture GUI.
- `scripts/calib.py stereo` resolves and prints the cam1/cam2 mono packages before capture, then prints both cameras' controls before it opens the stereo capture GUI.
- Expanded the persisted calibration control snapshot to include white-balance and focus controls when available.
- Added parsing for V4L2 boolean controls, so automatic white balance and continuous automatic focus are reported instead of incorrectly appearing unsupported.

## Verification

- `cd tools/calibration && uv run pytest`: 23 passed.
- `uv run scripts/calib.py mono cam1 --dry-run`: reports the controls step before the capture step.
- `uv run scripts/calib.py stereo --dry-run`: prints selected mono package paths, then the controls step, then the capture step.
- Before cameras were connected, the same command completed and labelled controls unsupported because `/dev/video0` and `/dev/video2` did not exist in the environment.
- With the cameras connected, `v4l2-ctl` identifies `/dev/video0` and `/dev/video2` as the two USB capture nodes. The control report reads their manual exposure, brightness, gain, white balance, and focus values.

## Note

Running `uv run --project tools/calibration pytest` from the repository root collected unrelated workspace tests and failed during dependency collection. The project-local command above uses the calibration project's `testpaths = ["tests"]` configuration and passed.
