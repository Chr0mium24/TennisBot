# Interface Layer Import Review - 2026-07-03

## Scope

- Source archive: `interface_layer_20260702.tar.gz`
- Extracted code path: `src/interface/`
- Generated Python cache files from the archive were not extracted.

## Plan

1. Inspect the archive contents before extraction.
2. Extract the interface source without generated cache files.
3. Review package structure, ROS messages, launch files, and runtime nodes.
4. Run lightweight syntax and ROS package discovery checks.
5. Run an isolated `colcon build` outside the repository tree.

## Extracted Packages

- `target_msgs`: ROS interface package containing:
  - `RawTarget.msg`
  - `ManagedTarget.msg`
  - `ChassisPosition.msg`
- `target_manager`: ROS Python package containing:
  - `target_manager_node`
  - `chassis_position_publisher_node`
  - launch files and default parameters

## Interface Summary

- Vision publishes `target_msgs/RawTarget` on `/target/raw`.
- `target_manager` validates, filters, buffers, and rate-limits predictions.
- `target_manager` publishes `target_msgs/ManagedTarget` on `/target/managed`.
- `chassis_position_publisher` converts `/robot/chassis_state` into
  `target_msgs/ChassisPosition` on `/robot/chassis_position`.
- The code uses ROS clock conventions and does not add local WebSim catch
  substitutes or frontend-only closed-loop behavior.

## Verification Results

- `colcon list --base-paths src/interface`
  - Passed.
  - Detected `target_msgs` as `ros.ament_cmake`.
  - Detected `target_manager` as `ros.ament_python`.
- `uv run -- python ... compile(...)`
  - Passed.
  - Compiled 6 Python files.
- `colcon build` with the default shell environment
  - Failed before package build due to environment mismatch.
  - ROS code generation used `/home/cr/miniconda3/bin/python3`.
  - That Python loaded an incompatible `em` module without `BUFFERED_OPT`.
- `colcon build` with system Python isolated from user site packages
  - Passed.
  - Command used `PATH=/usr/bin:/bin:/usr/sbin:/sbin:/opt/ros/humble/bin`
    and `PYTHONNOUSERSITE=1`.
  - Both `target_msgs` and `target_manager` built successfully.

## Notes

- No existing repository code outside `src/interface/` referenced the new
  topics at review time, so this import currently adds the interface layer but
  does not wire existing runtime components to it.
- The package manifests still have `license` set to `TODO`.
- Default `colcon build` in this shell is sensitive to the active conda Python;
  use the system Python environment for ROS Humble builds.
