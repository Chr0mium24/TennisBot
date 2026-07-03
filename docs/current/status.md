# TennisBot Current Status

Date: 2026-07-03

## Current Step

The project is moving from local operator visualization toward a headless ROS
vision runtime. The main tracked paths are now:

- `tools/calibration` for the fixed DFOptix ChArUco OpenCV capture GUI;
- `tools/yolo` for annotation, model package operations, and pure YOLO detect
  GUI;
- `tools/stereo` for local 4K stereo YOLO coordinate display;
- `packages/core` and `packages/contracts` for runtime algorithms and shared
  contracts;
- `src` for ROS2 interface packages, the TennisBot vision adapter, and the
  headless vision runtime.

## Ready Now

The ROS package path now includes:

- `tennisbot_vision_msgs/msg/ChassisPose` for timestamped `x/y/z/roll/pitch/yaw`;
- `tennisbot_interface_adapter` forwarding `/robot/chassis_state` to
  `/vision/chassis_pose`;
- `tennisbot_headless_vision` consuming `/vision/chassis_pose` and real stereo
  camera frames, then publishing `/vision/target_prediction`.

The current quick camera-device tool is:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
bun scripts/calib.ts preview
```

It prints average brightness for two USB cameras and can open a live preview
with shutter and brightness controls before calibration or headless vision runs.

## Important Gaps

The current local stereo calibration package is accepted and has no runtime
quality warning:

```text
stereo_rms_reprojection_px=0.2121
epipolar_rms_px=0.2568
rectification_y_p95_px=0.4296
baseline_m=0.1650
```

`tools/calibration` now mainlines the capture GUI, ChArUco mono solve, ChArUco
stereo solve, and runtime calibration package export.

The target real runtime is documented in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md). The
implemented code path still needs hardware or ROS/Gazebo validation. The main
remaining gaps are:

- measure and configure fixed chassis-to-camera extrinsics;
- use ROS clock for image capture stamps and chassis pose timestamps;
- verify real camera observations transform into field/interface coordinates
  before trajectory fitting;
- verify the adapter chain to `/target/raw` and `/target/managed`.

## Next Commands

Run pure YOLO camera detection:

```bash
cd tools/yolo
uv run --extra detect tennisbot-yolo detect-gui \
  --devices /dev/video0,/dev/video2 \
  --width 3840 \
  --height 2160 \
  --fourcc MJPG \
  --model ../../artifacts/models/tennis_ball_yolo/model.pt \
  --tile \
  --imgsz 1280 \
  --display-width 720
```

Run local stereo coordinate display:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts record --duration 60
bun scripts/stereo.ts gui --tile
bun scripts/stereo.ts gui --tile --record-run
bun scripts/stereo.ts replay
```

`record` stores raw left/right videos and timestamp metadata under
`runs/raw-stereo`. Without `--duration`, it continues until `q` or `esc` is
pressed in the preview window.

Dry-run the local stereo GUI defaults:

```bash
bun scripts/stereo.ts record --dry-run
bun scripts/stereo.ts gui --dry-run
```

Capture calibration frames:

```bash
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

Build and run the headless ROS chain:

```bash
source /opt/ros/humble/setup.bash
colcon build --base-paths src --packages-select \
  target_msgs target_manager tennisbot_vision_msgs \
  tennisbot_interface_adapter tennisbot_headless_vision
source install/setup.bash
ros2 launch tennisbot_interface_adapter interface_adapter.launch.py
ros2 launch tennisbot_headless_vision headless_vision.launch.py
```

Inspect runtime topics:

```bash
ros2 topic list -t
ros2 topic hz /vision/chassis_pose
ros2 topic hz /vision/target_prediction
ros2 topic echo /target/raw
```
