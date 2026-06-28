# Core Migration Wave 2 Result

Date: 2026-06-28

Branch: `refactor/core-migration`

## Scope

This branch migrates pure BallTrajectoryLab runtime math into data-only
TypeScript package APIs:

- rectified stereo epipolar error and disparity;
- row-major 3x4 projection matrix reprojection;
- average stereo reprojection diagnostics;
- rectified stereo triangulation without OpenCV;
- stereo detection pairing with epipolar, disparity, confidence, and temporal
  scoring;
- simple projectile prediction with trajectory samples and optional landing
  point.

The migration intentionally does not include Kalman filtering.

## Coordinate Convention

Core projectile prediction uses the same convention as the migrated
BallTrajectoryLab predictor:

- `x` is lateral position in meters;
- `y` is forward/depth position in meters;
- `z` is vertical-up position in meters;
- gravity acts in negative `z`;
- landing is solved against `landingSurfaceZMeters`, defaulting to `0`.

`TrajectoryPredictionOptions.landingSurfaceYMeters` is still accepted as a
temporary compatibility alias for the previous placeholder option name, but new
callers should use `landingSurfaceZMeters`.

## Projection Matrix Convention

`Matrix3x4` values are row-major:

```text
[p00, p01, p02, p03,
 p10, p11, p12, p13,
 p20, p21, p22, p23]
```

Projection maps a 3D point `[x, y, z, 1]` to homogeneous image coordinates.
Pixel coordinates are obtained by dividing projected `x` and `y` by projected
`w`.

## Tests Added

Focused Bun tests cover:

- rectified epipolar error;
- disparity;
- 3D reprojection through known 3x4 matrices;
- triangulation of a known rectified stereo point;
- average stereo reprojection error;
- timestamped stereo pair triangulation diagnostics;
- stereo pairing with competing candidates;
- temporal stereo pairing scoring;
- projectile prediction landing time and landing point;
- no-landing and invalid-input prediction behavior.

## Boundary Check

Edited paths are limited to:

- `packages/contracts/**`;
- `packages/core/**`;
- `docs/**`.

The following remain out of scope and must stay unchanged by this branch:

- `BallTrajectoryLab/**`;
- `CameraCalibLab/**`;
- `TennisBallDetectorLab/**`;
- `TennisWebSim/**`;
- `TennisBotCV/**`;
- `apps/live3d/**`;
- `.gitmodules`.
