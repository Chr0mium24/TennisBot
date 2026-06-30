# Calibration Solve Export Plan

Date: 2026-06-30

## Goal

Mainline calibration solving in `tools/calibration` so captured ChArUco mono and
stereo sessions can be converted into TennisBot runtime calibration packages.

## Scope

- Add `camera-calib-lab solve mono`.
- Add `camera-calib-lab solve stereo`.
- Export runtime package files compatible with `packages/core` and Live3D:
  - mono: `package.json`, `camera.json`, `verification.json`,
    `calibration_opencv.yaml`, `summary.md`, `review.html`;
  - stereo: `package.json`, `cam1.json`, `cam2.json`, `stereo.json`,
    `rectification.json`, `verification.json`, `calibration_opencv.yaml`,
    `summary.md`, `review.html`.
- Support current GUI capture sessions and existing observation JSON inputs.
- Add focused Python tests using synthetic ChArUco observations.
- Update current docs and record implementation results.

## Non-Goals

- Do not claim physical calibration quality without real captured target frames.
- Do not add local receiving-loop substitute logic.
- Do not modify archived historical records except adding this dated plan/result.

## Acceptance

- `uv run python -m unittest discover -s tests` passes in `tools/calibration`.
- `camera-calib-lab solve mono --help` works.
- `camera-calib-lab solve stereo --help` works.
- The solver can write mono and stereo runtime package directories.
