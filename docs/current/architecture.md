# TennisBot Current Architecture

Date: 2026-07-03

## Current Shape

TennisBot is a local-machine-first workspace. The active tracked code lives in
top-level `packages/`, `scripts/`, `src/`, and `tools/`.

```text
TennisBot/
  packages/
    contracts/       shared TypeScript data contracts
    core/            artifact loaders, stereo pairing, triangulation helpers
  src/
    interface/       imported ROS2 target interface packages
    tennisbot_*      repository-owned ROS2 vision messages, adapter, runtime
  tools/
    calibration/     fixed DFOptix ChArUco OpenCV capture GUI
    yolo/            annotation, YOLO package, pure detection GUI
    stereo/          raw stereo recorder and local stereo coordinate GUI
  scripts/
    yolo.ts          root launcher for the YOLO annotation frontend/backend
    stereo.ts        root launcher for stereo record/preview/replay
  artifacts/         ignored local runtime artifacts
  docs/
    current/         current operational truth
    reports/         business/report artifacts
    archive/         dated plans, probes, reviews, and historical results
```

Ignored legacy lab code can still exist under local `desperate/` directories,
but it is no longer the main tracked architecture.

## Tool Boundaries

### `tools/calibration`

Owns the mainline OpenCV calibration capture GUI for this project target:

- fixed DFOptix ChArUco target profile
  `dfoptix_charuco_14x9_square15mm_marker11_25mm`;
- `DICT_5X5_100`, 14 x 9 squares, 15 mm squares, 11.25 mm markers;
- mono capture GUI command;
- stereo capture GUI command;
- mono ChArUco solve and runtime package export;
- stereo ChArUco solve and runtime package export;
- USB camera brightness checks;
- capture quality checks for full-corner coverage, brightness, sharpness,
  stability, position buckets, and dwell capture;
- `session.json` capture sessions with saved frame paths plus per-frame
  metadata and summary artifacts.

Current commands:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

### `tools/yolo`

Owns tennis-ball detector tooling:

- local annotation frontend/backend via `tennisbot-yolo annotate`;
- runtime model package create/verify;
- pure OpenCV YOLO detection GUI via `tennisbot-yolo detect-gui`.

The annotation and model-package paths use the default `uv sync` environment and
do not require Torch, CUDA, or Ultralytics. `detect-gui` is isolated behind the
optional `detect` extra.

It does not own stereo geometry, calibration, camera/world transforms, runtime
state, or trajectory prediction.

Current commands:

```bash
bun scripts/yolo.ts annotate
cd tools/yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
uv run --extra detect tennisbot-yolo detect-gui --devices /dev/video0,/dev/video2 --model ../../artifacts/models/tennis_ball_yolo/model.pt --tile
```

### `tools/stereo`

Owns the local OpenCV stereo-coordinate GUI:

- opens two USB cameras at 4K MJPG by default;
- runs YOLO tennis-ball detection;
- reads the current runtime stereo calibration package;
- rectifies detected centers, pairs candidates, triangulates a camera-frame
  3D point, and displays x/y/z/range plus stereo diagnostics.
- records raw left/right stereo video under `runs/raw-stereo`;
- records long local sessions under `runs/stereo`;
- serves a local replay frontend that lists records, selects time windows with
  UI sliders, and renders camera-frame 3D points plus prediction curves.

Current command:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui --tile
bun scripts/stereo.ts gui --tile --record-run
bun scripts/stereo.ts replay
```

It displays camera-frame geometry only: x right, y down, z forward.

### `packages/core`

Owns TypeScript artifact validation and stereo geometry helpers:

- YOLO and stereo calibration artifact metadata loaders;
- stereo detection pairing with rectification, disparity/depth filtering, and
  reprojection diagnostics;
- rectified stereo triangulation helpers.

It has no browser UI, OpenCV GUI, camera device access, dataset management, or
training code. The active ROS trajectory predictor lives in
`src/tennisbot_headless_vision`.

### `src`

Owns tracked vision runtime integration:

- external `target_msgs` and `target_manager` come from the sourced control
  workspace (`/home/cr/tennis_robot_ws/install`);
- `src/tennisbot_headless_vision`: stereo vision runtime that
  consumes camera frames plus `/robot/chassis_position` and publishes
  `/target/raw`, with optional timestamped runtime logging.

The nominal raw target path is 30 Hz. The managed target output remains at most
10 Hz by design.

### Target Vision Runtime

The real runtime is a vision runtime, not a frontend. The runtime
design is documented in
[Vision Runtime](vision_runtime.md).

The node consumes stereo camera frames and timestamped chassis pose, transforms
triangulated ball points into the field/interface frame, fits the trajectory,
and publishes `/target/raw`. It publishes nothing without real camera
observations and recent `/robot/chassis_position` samples.

## Runtime Flow

```text
1. tools/calibration captures mono/stereo ChArUco sessions
2. tools/calibration solves mono/stereo calibration packages under artifacts/calibration/...
3. tools/yolo creates or verifies artifacts/models/tennis_ball_yolo
4. tools/stereo can run the local OpenCV 4K stereo coordinate GUI
5. tennisbot_headless_vision consumes `/robot/chassis_position`
6. tennisbot_headless_vision reads two camera streams
7. the node runs YOLO, stereo pairing, triangulation, field-frame transforms,
   and trajectory prediction
8. the node publishes `/target/raw`
9. external `target_manager` publishes `/target/managed` for the planner/state
   machine
```

When runtime logging is enabled, vision runtime sessions are written under
`runs/vision-runtime/<session>/` with left/right video, frame timestamps, chassis
position, YOLO detections, selected observations, raw targets, and runtime
events.

## Current Validation State

The current local stereo package under `artifacts/calibration/stereo_cam1_cam2`
is accepted with no runtime quality warning:

```text
stereo_rms_reprojection_px=0.212138
epipolar_rms_px=0.256774
rectification_y_p95_px=0.429620
baseline_m=0.164989
```

The epipolar metric is computed after undistorting points and evaluating the
essential-matrix constraint in normalized coordinates, converted back to pixels
by average focal length. The remaining physical gap is the measured
chassis-to-camera extrinsic and full real chassis validation. The
vision runtime node includes a configurable `T_chassis_camera`, but the default
translation is only a placeholder until measured on the mounted rig.

## Main Commands

Camera brightness sanity check:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
bun scripts/calib.ts preview
```

Build and launch the ROS runtime:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_headless_vision --symlink-install
source install/setup.bash
ros2 launch tennisbot_headless_vision headless_vision.launch.py
ros2 launch target_manager target_manager.launch.py
```

One-shot or logged runtime launcher:

```bash
bun scripts/headless.ts run --record --session test01 --tile
bun scripts/headless.ts task --task-id 42 --session catch42 --tile
```

Start the local OpenCV stereo-coordinate GUI:

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui --tile
```

Verify core packages:

```bash
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
```

Inspect ROS interfaces and topics:

```bash
ros2 interface show target_msgs/msg/ChassisPosition
ros2 interface show target_msgs/msg/RawTarget
ros2 interface show target_msgs/msg/ManagedTarget
ros2 topic list -t
ros2 topic echo /robot/chassis_position
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

## Remaining Engineering Work

- Recalibrate after the cameras are mounted in their real physical positions.
- Measure and configure the real `T_chassis_camera` extrinsics.
- Verify `/target/raw` -> `/target/managed` with real chassis pose and control
  links.
