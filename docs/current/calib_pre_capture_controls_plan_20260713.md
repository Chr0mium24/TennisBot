# Calibration pre-capture parameter reporting plan

## Goal

Before opening a mono or stereo calibration capture GUI, print the current V4L2 camera controls in the terminal. Before a stereo capture-and-solve run opens its GUI, also print the accepted mono calibration packages selected for cam1 and cam2.

## Steps

1. Add a calibration CLI command that reports a deterministic set of current V4L2 controls, including exposure, brightness, gain, white balance, and focus controls when supported.
2. Run that command as a pre-capture step in the wrapper for mono and stereo calibration; resolve and print stereo mono inputs before capture.
3. Add unit coverage for the report and wrapper command ordering, run the calibration test suite, and record the result.
