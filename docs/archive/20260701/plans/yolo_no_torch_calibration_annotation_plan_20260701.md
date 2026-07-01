# YOLO No-Torch Calibration/Annotation Plan 2026-07-01

## Goal

Make it explicit that calibration and the YOLO annotation service can run
without installing Torch, CUDA, Ultralytics, or NVIDIA Python packages.

## Scope

1. Document the no-Torch path for `tools/calibration`.
2. Document the no-Torch path for `tools/yolo annotate` and model package
   commands.
3. Keep `detect-gui` as the only `tools/yolo` command that needs the optional
   `detect` extra.
4. Verify with isolated `uv` environments that default sync does not install
   `torch`, `ultralytics`, or CUDA/NVIDIA packages.

## Non-Goals

- Do not remove YOLO detection GUI support.
- Do not change calibration, detection, or stereo runtime behavior.
- Do not claim real stereo catching-loop validation without ROS/Gazebo.
