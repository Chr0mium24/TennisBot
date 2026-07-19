# TennisBot Current Status

Date: 2026-07-19

The camera-facing refactor is implemented on the current branch. Operators now
use `camera`, `calib`, `record`, and `test`; the mixed stereo tool has been
removed. Camera identity/control configuration and runtime stereo algorithms
are shared through `packages/vision-python`.

Non-hardware tests cover camera mapping, recording plans/session timing,
calibration command construction, YOLO ROI behavior, stereo matching and
triangulation, test CLI contracts, and attachable recording without opening a
camera.

Still required on the target hardware:

- camera list/check/preview and profile readback;
- online mono/stereo calibration;
- headless and GUI mono/stereo recording;
- headless and GUI YOLO/triangulation;
- raw/overlay test recordings and timestamp review;
- read-only chassis-position validation against sourced ROS;
- ROS runtime build and real camera/pose validation.

No non-ROS result is evidence of a real catch-loop validation.
