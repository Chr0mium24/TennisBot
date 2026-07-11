# TennisBot Current Status

Date: 2026-07-03

## Current Step

The project is moving from local operator visualization toward a vision
runtime. The main tracked paths are now:

- `tools/calibration` for the fixed DFOptix ChArUco OpenCV capture GUI;
- `tools/yolo` for annotation, model package operations, and pure YOLO detect
  GUI;
- `tools/stereo` for local 4K stereo YOLO coordinate display;
- `packages/core` and `packages/contracts` for TypeScript artifact/geometry
  helpers and shared contracts;
- `src` for the vision runtime.

## Ready Now

The runtime package path now includes:

- `tennisbot_vision_runtime` consuming `/robot/chassis_position` and real
  stereo camera frames, then publishing `target_msgs/RawTarget` on
  `/target/raw`;
- external `target_msgs` and `target_manager` from the sourced
  `/home/cr/tennis_robot_ws` control workspace;
- external `target_manager` consuming `/target/raw` and publishing
  `/target/managed`;
- `scripts/vision-runtime.py` for logged runtime launches and single-task runs with
  caller-specified `task_id`.

The current quick camera-device tool is:

```bash
uv run scripts/calib.py brightness
uv run scripts/calib.py brightness --devices /dev/video0,/dev/video2
uv run scripts/calib.py preview
```

It prints average brightness for two USB cameras and can open a live preview
with shutter and brightness controls before calibration or vision runtime runs.

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
[Vision Runtime](vision_runtime.md). The implemented code path still needs
hardware validation. The main
remaining gaps are:

- measure and configure fixed chassis-to-camera extrinsics;
- provide chassis yaw in `target_msgs/ChassisPosition`; see
  [Chassis Pose Input Contract](chassis_pose_input_gap.md);
- use ROS clock for image capture stamps and chassis pose timestamps;
- verify real camera observations transform into field/interface coordinates
  before trajectory fitting;
- verify the direct `/target/raw` and `/target/managed` chain.

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
uv run scripts/stereo.py record
uv run scripts/stereo.py record --duration 60
uv run scripts/stereo.py gui --tile
uv run scripts/stereo.py gui --tile --record-run
uv run scripts/stereo.py replay
```

`record` stores raw left/right videos and timestamp metadata under
`runs/raw-stereo`. Without `--duration`, it continues until `q` or `esc` is
pressed in the preview window.

Dry-run the local stereo GUI defaults:

```bash
uv run scripts/stereo.py record --dry-run
uv run scripts/stereo.py gui --dry-run
```

Capture calibration frames:

```bash
uv run scripts/calib.py preview
uv run scripts/calib.py mono cam1
uv run scripts/calib.py mono cam2
uv run scripts/calib.py stereo
```

Build and run the vision runtime chain:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
source install/setup.bash
ros2 launch tennisbot_vision_runtime vision_runtime.launch.py
ros2 launch target_manager target_manager.launch.py
```

Logged or single-task run:

```bash
uv run scripts/vision-runtime.py run --record --session test01 --tile
uv run scripts/vision-runtime.py task --task-id 42 --session catch42 --tile
```

Inspect runtime topics:

```bash
ros2 topic list -t
ros2 topic hz /robot/chassis_position
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```
