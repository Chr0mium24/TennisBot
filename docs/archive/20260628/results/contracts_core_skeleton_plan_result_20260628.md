# Contracts And Core Skeleton Plan And Result

Date: 2026-06-28

Branch: `refactor/contracts-core-skeleton`

## Plan

1. Create top-level `packages/contracts` as a TypeScript/Bun package for plain
   data contracts used by the future live runtime.
2. Create top-level `packages/core` as a TypeScript/Bun package for conservative
   runtime algorithm APIs.
3. Keep triangulation and prediction behavior explicit placeholders until
   BallTrajectoryLab code is migrated and tested behind the new data contracts.
4. Add focused Bun tests for contract literals and small pinhole projection
   helpers.

## Result

- Added contracts for camera intrinsics, stereo extrinsics, YOLO 2D detections,
  timestamped stereo detection pairs, triangulated 3D ball points, prediction
  curves, landing points, and artifact references.
- Added core API placeholders for stereo triangulation, trajectory prediction,
  and runtime artifact loading interfaces.
- Added simple pinhole projection and image-point normalization helpers as the
  only implemented geometry behavior.

## BallTrajectoryLab Migration Notes

Later `packages/core` migration should start with:

- `BallTrajectoryLab/src/ball_trajectory_lab/stereo_types.py` and
  `types.py` for existing data shape comparisons against the new contracts.
- `BallTrajectoryLab/src/ball_trajectory_lab/stereo_geometry.py` for projection
  and stereo triangulation math.
- `BallTrajectoryLab/src/ball_trajectory_lab/stereo_fusion.py` for synchronized
  stereo detection pairing and 3D point construction policy.
- `BallTrajectoryLab/src/ball_trajectory_lab/state_estimator_3d.py` for 3D
  ball state and velocity estimation.
- `BallTrajectoryLab/src/ball_trajectory_lab/predictor_3d.py` for trajectory
  curve and landing prediction behavior.

Rendering, report generation, datasets, calibration solving, and scripts should
remain outside `packages/core` unless a later task explicitly defines a shared
runtime interface for them.
