# Local Runtime Operator Runbook

Date: 2026-07-03

## Scope

This runbook is the local-machine sequence for the current local reference
tools. The target real runtime is the headless ROS vision path documented in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md).

1. `tools/calibration` OpenCV GUI for fixed DFOptix ChArUco mono/stereo capture.
2. `tools/yolo` for pure YOLO detection and runtime model packages.
3. `tools/stereo` for local OpenCV 4K stereo YOLO coordinate display.
4. `src/tennisbot_headless_vision` for the ROS headless camera-to-target
   runtime path.

The real catch loop still requires ROS/Gazebo or real chassis pose and control
links. Local camera tools are diagnostics only.

## Start Surfaces

From the repository root:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_headless_vision --symlink-install
source install/setup.bash
```

Start the headless vision node and external target manager in separate
terminals:

```bash
ros2 launch tennisbot_headless_vision headless_vision.launch.py
ros2 launch target_manager target_manager.launch.py
```

Or start the same chain through the Bun runtime launcher:

```bash
bun scripts/headless.ts run
bun scripts/headless.ts run --record --session test01 --tile
bun scripts/headless.ts task --task-id 42 --session catch42 --tile
```

Start the local stereo coordinate GUI:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui --tile
```

## Calibration Order

Before taking calibration frames, check camera brightness/order:

```bash
bun scripts/calib.ts brightness
```

Open the live camera preview if exposure or UVC brightness needs tuning:

```bash
bun scripts/calib.ts preview
```

Use the mainline OpenCV GUI in order:

1. Confirm the fixed physical DFOptix ChArUco board is clean, flat, and matches
   the configured `15 mm` square / `11.25 mm` marker dimensions.
2. Tune camera shutter/brightness in `bun scripts/calib.ts preview` if the
   view is too dark, saturated, or noisy.
3. `bun scripts/calib.ts mono cam1` for the left mono capture and solve.
4. `bun scripts/calib.ts mono cam2` for the right mono capture and solve.
5. `bun scripts/calib.ts stereo` for stereo capture, solve, and runtime package
   export under `artifacts/calibration/stereo_cam1_cam2`.

## Headless ROS Order

After the stereo package verifies and the camera rig is mounted:

1. Measure and set `camera_translation_m` and `camera_rotation_rpy_rad` in
   `src/tennisbot_headless_vision/config/headless_vision.yaml`.
2. Confirm the interface bridge is publishing `/robot/chassis_position`
   as `target_msgs/ChassisPosition`.
3. Set `chassis_position_input_frame` in
   `src/tennisbot_headless_vision/config/headless_vision.yaml` to `field`
   or `cartesian`.
4. Launch `tennisbot_headless_vision` and confirm it publishes `/target/raw`
   only when a real ball is detected in both cameras and recent chassis
   position is available.
5. Launch external `target_manager` from the sourced control workspace and
   confirm `/target/managed` before enabling chassis planner behavior.
6. For evidence capture, prefer `bun scripts/headless.ts run --record` or
   `bun scripts/headless.ts task --task-id <id> --session <name>` so the video,
   chassis position, YOLO detections, selected observations, and raw targets
   share one timestamped session directory.

## Local Stereo GUI Order

After the stereo package verifies:

1. Run `bun scripts/stereo.ts gui --dry-run` to confirm default devices,
   artifact paths, and 4K capture settings.
2. Run `bun scripts/stereo.ts record` when raw left/right stereo video is
   needed. It writes under `runs/raw-stereo` and stops on `q` or `esc`; use
   `--duration <seconds>` only for an automatic stop.
3. Run `bun scripts/stereo.ts gui --tile` for YOLO detection on small 4K balls.
4. Add `--record-run` for long trajectory point/detection recording under
   `runs/stereo`.
5. Read the right panel as left-camera-frame coordinates: x right, y down,
   z forward.

Open the replay frontend:

```bash
bun scripts/stereo.ts replay
```

The replay page lists recorded sessions and uses two UI range sliders for the
selected trajectory window. Do not pass replay time windows through CLI flags.

## Current Runtime Evidence

Historical browser/runtime reports remain under `docs/archive/`. Current
runtime evidence should come from ROS topics and logs from the headless chain.
