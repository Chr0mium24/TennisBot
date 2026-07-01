# Local Physical Validation Checklist

Date: 2026-06-29

## Purpose

This is the operator checklist for finishing the local-machine TennisBot loop.
It starts after the software preflight has passed and the Live3D browser
surface is available:

```text
Live3D:          http://127.0.0.1:5178/
```

The checklist is complete only when Live3D reaches `prediction-ready` with a
real visible tennis ball.

## 0. Software Preflight

Run from the repository root:

```bash
bun scripts/operator-preflight.ts --output docs/local_runtime_preflight_YYYYMMDD.md
```

Pass condition:

- Live3D surface returns 200.
- YOLO package verifies.
- Stereo calibration package verifies.
- `/dev/video0` and `/dev/video2` are present.

## 1. Target

Generate or select the DFOptix ChArUco target from the retained CameraCalibLab
workflow:

```bash
cd desperate/CameraCalibLab
uv run camera-calib-lab target generate --help
```

Expected artifacts:

- `artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png`
- `artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.svg`
- `artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json`
- `docs/calibration_charuco_target_sheet_YYYYMMDD.md`

Print gate:

- Print the SVG at 100% scale.
- Measure one printed square.
- Continue only if one square is 15.0 mm.
- Record the measurement in
  `artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json`.

If the printed square is not 15.0 mm, fix printer scaling and reprint before
capturing any camera frames.

## 2. Cam1 Mono

Use the original OpenCV GUI to capture Cam1 mono frames and produce the mono
calibration package:

```bash
cd desperate/CameraCalibLab
uv run camera-calib-lab capture charuco-auto-gui \
  --config configs/dfoptix_charuco_15mm_capture.yaml \
  --output captures/local/dfoptix_charuco_cam1_session \
  --calibration-output runs/calibrations/dfoptix_charuco_cam1 \
  --views 30 \
  --device /dev/video0
```

Pass condition:

- CameraCalibLab reports accepted capture/detection/solve results.
- The workflow produces `artifacts/calibration/cam1/package.json`.
- The mono package has `hardware_validated: true`.

Default solve gate:

- At least 8 accepted views.
- RMS reprojection error at or below 1.0 px.

If this fails, recapture Cam1 with the target flat, sharp, bright, and visible
at different image positions and tilts.

## 3. Cam2 Mono

Use the same OpenCV mono capture flow for Cam2, changing the device and output
paths for the second camera.

Pass condition:

- CameraCalibLab reports accepted capture/detection/solve results.
- The workflow produces `artifacts/calibration/cam2/package.json`.
- The mono package has `hardware_validated: true`.

Default solve gate:

- At least 8 accepted views.
- RMS reprojection error at or below 1.0 px.

If this fails, recapture Cam2 before attempting stereo solve.

## 4. Stereo

Use the original OpenCV stereo capture GUI:

```bash
cd desperate/CameraCalibLab
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --config configs/dfoptix_charuco_15mm_capture.yaml \
  --output captures/local/dfoptix_stereo_charuco_auto_session \
  --calibration-output runs/calibrations/dfoptix_stereo_charuco_auto \
  --views 30 \
  --left-device /dev/video0 \
  --right-device /dev/video2
```

Pass condition:

- CameraCalibLab reports accepted capture/detection/solve results.
- The workflow produces `artifacts/calibration/stereo_cam1_cam2/package.json`.
- The stereo package has `hardware_validated: true`.

Default solve gate:

- At least 12 accepted stereo pairs in the GUI preset.
- Stereo RMS reprojection error at or below 2.0 px.
- Non-zero baseline in `stereo.json`.

If this fails, recapture stereo with the target visible in both cameras at the
same time. Do not reuse a stereo capture where one side misses the board.

## 5. Live3D

Open Live3D after the stereo package verifies.

Runtime gates:

- Start both USB camera streams.
- Load the YOLO package from `artifacts/models/tennis_ball_yolo`.
- Load the stereo package from `artifacts/calibration/stereo_cam1_cam2`.
- Put a tennis ball clearly inside both camera views.
- Watch the readiness gates reach:
  - left YOLO detection;
  - right YOLO detection;
  - stereo triangulated ball point;
  - prediction curve and landing point.

Final browser check:

Pass condition:

- The generated hardware report reaches `prediction-ready`.

If the report shows readable frames but blocked YOLO detections, adjust lighting,
camera aim, ball visibility, or the model package before declaring the physical
loop complete.

## Current Status

As of 2026-06-29, the calibration web service has been removed. The
remaining acceptance work is physical: print and measure the target, capture
real accepted mono/stereo calibration sessions with the OpenCV GUI, then run
Live3D with a visible tennis ball.
