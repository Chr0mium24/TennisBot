# Headless ROS Runtime And Live3D Removal Plan

Date: 2026-07-03

## Goal

Remove the active Live3D frontend path and make the ROS headless vision chain
the main runtime path for real operation.

## Scope

- Delete `apps/live3d/` and `scripts/live3d.ts`.
- Add a vision-side full chassis pose message with timestamp, position, and yaw.
- Extend `tennisbot_interface_adapter` so `/robot/chassis_state` can produce
  `/vision/chassis_pose`.
- Add a `tennisbot_headless_vision` ROS package that:
  - reads stereo cameras;
  - timestamps captured frames with ROS clock immediately after acquisition;
  - reuses the OpenCV stereo detector/matcher path;
  - transforms camera-frame ball points into the field/interface frame;
  - fits a gravity-based trajectory;
  - publishes `/vision/target_prediction`.
- Update current docs and command entry points to point at the headless ROS
  chain instead of Live3D.

## Non-Goals

- Do not create simulated target predictions or a local chassis substitute.
- Do not claim real catch-loop validation without ROS/Gazebo or real chassis
  pose/control links.
- Do not touch unrelated YOLO augmentation work already present in the
  worktree.

## Validation

- Python syntax compile for changed ROS Python packages.
- ROS `colcon build` for the interface, adapter, and headless vision packages.
- ROS interface and launch metadata checks after build.
- Scan current docs and active code for obsolete Live3D commands.
