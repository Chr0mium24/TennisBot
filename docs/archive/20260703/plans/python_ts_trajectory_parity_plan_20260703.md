# Python/TS Trajectory Parity Plan

Date: 2026-07-03

## Goal

Align the ROS Python trajectory predictor with the TypeScript
`packages/core` trajectory algorithm so the headless ROS runtime uses the same
fixed-gravity model selection behavior as the TS core path.

## Scope

- Port the TS `predictTrajectory` state estimator into
  `src/tennisbot_headless_vision/tennisbot_headless_vision/trajectory.py`.
- Keep the existing ROS-facing `predict_target(...)` API stable.
- Default to the same `auto` selection order:
  - RANSAC guarded weighted least squares when enough samples exist;
  - weighted least squares when the RANSAC guard cannot run;
  - two-frame fixed-gravity fallback.
- Preserve configured ROS limits:
  - `target_plane_z`;
  - `gravity_mps2`;
  - `min_predicted_time`;
  - `max_predicted_time`;
  - `min_sigma_m`.
- Add focused parity tests that compare Python output with checked TS fixture
  expectations for identical input trajectories.

## Non-Goals

- Do not introduce a TypeScript runtime dependency into the ROS node.
- Do not change camera capture, YOLO detection, stereo matching, ROS topics, or
  coordinate transforms.
- Do not claim real catch-loop validation without ROS/Gazebo or hardware.

## Verification

- Run Python trajectory tests for the headless package.
- Run `packages/core` Bun tests to ensure the TS reference path still passes.
- Record commands and results in a Markdown result document.
