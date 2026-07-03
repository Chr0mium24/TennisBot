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
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select \
  target_manager tennisbot_vision_msgs \
  tennisbot_interface_adapter tennisbot_headless_vision
source install/setup.bash
```

Start the ROS adapter and headless vision node in separate terminals:

```bash
ros2 launch tennisbot_interface_adapter interface_adapter.launch.py
ros2 launch tennisbot_headless_vision headless_vision.launch.py
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
2. Confirm `/robot/chassis_state` is publishing
   `[x_m, y_m, v_mps, phi_rad, yaw_rad, ground_speed_mps]`.
3. Set `chassis_state_input_frame` in
   `src/tennisbot_interface_adapter/config/interface_adapter.yaml` to `field`
   or `cartesian`.
4. Launch `tennisbot_interface_adapter` and confirm `/vision/chassis_pose` is
   present at nominal 30 Hz.
5. Launch `tennisbot_headless_vision` and confirm it publishes
   `/vision/target_prediction` only when a real ball is detected in both
   cameras and a recent pose is available.
6. Confirm `/target/raw` and `/target/managed` before enabling chassis planner
   behavior.

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
