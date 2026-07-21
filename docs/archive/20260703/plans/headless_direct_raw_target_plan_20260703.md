# Headless Direct RawTarget Plan

Date: 2026-07-03

## Goal

Collapse the main runtime chain so `tennisbot_headless_vision` publishes the
external raw target interface directly:

```text
/robot/chassis_state
  -> tennisbot_headless_vision

stereo cameras
  -> tennisbot_headless_vision
  -> /target/raw
  -> target_manager
  -> /target/managed
```

The runtime should no longer require a separate `tennisbot_interface_adapter`
node for the main camera-to-target path.

## Scope

1. Move `/robot/chassis_state` parsing and field/cartesian conversion into the
   headless vision node.
2. Change the headless vision node publisher from
   `tennisbot_vision_msgs/TargetPrediction` on `/vision/target_prediction` to
   `target_msgs/RawTarget` on `/target/raw`.
3. Update headless runtime configuration and package dependencies.
4. Update current run docs so the normal startup path is headless vision plus
   `target_manager`.
5. Keep the existing adapter package in the tree as a compatibility/debugging
   bridge, but remove it from the documented main runtime startup path.

## Non-Goals

- Do not add local catch substitutes or non-ROS closed-loop logic.
- Do not remove `target_manager`.
- Do not change YOLO training, augmentation, calibration, or stereo GUI tools.
- Do not claim real catch-loop validation without real ROS/chassis or real chassis
  control links.

## Verification

- Compile the modified Python modules.
- Run headless trajectory unit tests through `uv`.
- Run ROS package discovery/build checks when ROS and the external
  `target_msgs` workspace are available.
- Save verification results in a Markdown result document.
