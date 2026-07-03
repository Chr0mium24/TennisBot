# Headless Runtime Logging And Adapter Removal Plan

Date: 2026-07-03

## Goal

Remove the old optional ROS compatibility bridge and make the direct headless
runtime easier to operate and debug.

Target main chain:

```text
/robot/chassis_state + stereo cameras
  -> tennisbot_headless_vision
  -> /target/raw
  -> target_manager
  -> /target/managed
```

## Scope

1. Delete `tennisbot_interface_adapter` and the unused vision-side message
   package from the active `src` tree.
2. Update current docs so they no longer describe the adapter as available.
3. Add optional runtime logging inside `tennisbot_headless_vision`:
   - timestamped left/right video;
   - timestamped chassis state and converted field pose;
   - YOLO detections, stereo match diagnostics, selected camera point, and
     selected field point;
   - published raw target messages.
4. Add a Bun script for the headless runtime:
   - normal main-chain launch;
   - optional logging;
   - single-task mode with caller-specified `task_id`.

## Non-Goals

- Do not add simulated catch logic or local chassis tracking substitutes.
- Do not change YOLO training or augmentation code.
- Do not require the local stereo GUI to publish ROS topics.
- Do not claim closed-loop validation without ROS/Gazebo or real chassis
  control links.

## Verification

- Compile modified Python.
- Run headless trajectory tests.
- Run Bun script help and dry-run paths.
- Run ROS build/launch checks when `target_msgs` is available.
- Save results in a Markdown result document.
