# Calibration Solve Export Result

Date: 2026-06-30

## Summary

Implemented mainline ChArUco calibration solving and runtime package export in
`tools/calibration`.

New commands:

```bash
uv run camera-calib-lab solve mono
uv run camera-calib-lab solve stereo
```

## Implemented

- `solve mono` can read either:
  - a current `camera-calib-lab capture charuco-auto-gui` session directory; or
  - an existing `observations.json`.
- `solve stereo` can read either:
  - a current `camera-calib-lab capture stereo-charuco-auto-gui` session
    directory; or
  - an existing `observations.json`.
- Mono export writes:
  - `package.json`
  - `camera.json`
  - `verification.json`
  - `calibration_opencv.yaml`
  - `summary.md`
  - `review.html`
- Stereo export writes:
  - `package.json`
  - `cam1.json`
  - `cam2.json`
  - `stereo.json`
  - `rectification.json`
  - `verification.json`
  - `calibration_opencv.yaml`
  - `summary.md`
  - `review.html`
- Stereo metrics include:
  - `stereo_rms_reprojection_px`
  - `epipolar_rms_px`
  - `rectification_y_p95_px`
  - `baseline_m`
  - `matched_point_count_min`

## Verification

Commands:

```bash
cd tools/calibration
uv run python -m unittest discover -s tests
uv run camera-calib-lab solve mono --help
uv run camera-calib-lab solve stereo --help
uv run python -m compileall -q src

cd ../../packages/core
bun test

cd ../contracts
bun test

cd ../..
git diff --check
```

Results:

```text
tools/calibration unittest: 2 passed.
solve mono help: passed.
solve stereo help: passed.
compileall: passed.
packages/core bun test: 23 passed, 0 failed.
packages/contracts bun test: 4 passed, 0 failed.
git diff --check: passed.
```

## Notes

The implementation proves the software solve/export path with synthetic ChArUco
observations. Real physical acceptance still requires new visible fixed-board
captures from the actual mounted cameras. No real ROS/chassis receiving-loop claim is
made by this result.
