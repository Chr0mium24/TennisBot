# Multi-Agent Refactor Wave 3 Live3D Core Fixture Result

Date: 2026-06-28

Branch:

```text
refactor/live3d-core-fixture
```

## Summary

`apps/live3d` fixture mode now uses shared contract-shaped fixture data and runs
the fixture path through `packages/core`:

```text
fixture detections -> selectBestStereoPair -> triangulateStereoPair
-> predictTrajectory -> rendered camera overlays and 3D fixture scene
```

This remains fixture mode only. It does not validate USB cameras, real YOLO
inference, real calibration artifacts, real stereo tracking, real
triangulation, or real prediction.

## Changes

- Added in-memory `StereoCalibration` fixture data with rectified projection
  matrices.
- Replaced hand-coded camera detections with `YoloDetection2D` fixtures.
- Built a short fixture point history by selecting stereo pairs and
  triangulating them through `packages/core`.
- Rendered the latest triangulated point, prediction curve, and landing point
  from core outputs.
- Updated tests to assert a stereo match, 3D point, prediction curve, and
  landing point are produced by fixture construction.

## Verification

Verification commands are run before handoff:

```bash
cd apps/live3d && bun run typecheck && bun test && bun run build
cd packages/core && bun test && bun run typecheck
cd packages/contracts && bun test && bun run typecheck
git diff --check
git diff --name-only main..HEAD
```

## Boundary

This branch intentionally leaves these paths unchanged:

- `packages/core/**`
- `packages/contracts/**`
- `BallTrajectoryLab/**`
- `CameraCalibLab/**`
- `TennisBallDetectorLab/**`
- `TennisWebSim/**`
- `TennisBotCV/**`
- `.gitmodules`
