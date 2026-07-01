# Auto Exposure Readback Probe Plan

## Goal

Check the `exposure_time_absolute` readback while both calibration cameras are
running in auto exposure mode.

## Procedure

1. Set `/dev/video0` and `/dev/video2` to `auto_exposure=3` and
   `brightness=64`.
2. Open each camera stream at `1280x720`.
3. Read 90 frames per camera.
4. Query `auto_exposure` and `exposure_time_absolute` at frames
   1, 10, 30, 60, and 90.
5. Record final average grayscale brightness.
6. Capture a photo pair comparing `auto_exposure=3` against
   `auto_exposure=1, exposure_time_absolute=200` with the same brightness
   setting.
