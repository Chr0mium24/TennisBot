# TennisBot Current Architecture

Date: 2026-07-03

## Current Shape

TennisBot is a local-machine-first workspace. The active tracked code lives in
top-level `apps/`, `packages/`, `scripts/`, `src/`, and `tools/`.

```text
TennisBot/
  apps/
    live3d/          browser USB stereo camera runtime, temporary/reference UI
  packages/
    contracts/       shared TypeScript data contracts
    core/            artifact loaders, stereo pairing, triangulation, prediction
  src/
    interface/       imported ROS2 target interface packages
    tennisbot_*      repository-owned ROS2 vision interface adapter packages
  tools/
    calibration/     fixed DFOptix ChArUco OpenCV capture GUI
    yolo/            annotation, YOLO package, pure detection GUI
    stereo/          raw stereo recorder and local stereo coordinate GUI
  scripts/
    live3d.ts        single root launcher/status check for Live3D
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

It does not own stereo geometry, calibration, camera/world transforms, Live3D
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
- runs YOLO or HSV tennis-ball detection;
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

Owns pure runtime algorithms and artifact validation:

- YOLO and stereo calibration artifact metadata loaders;
- stereo detection pairing with rectification, disparity/depth filtering, and
  reprojection diagnostics;
- rectified stereo triangulation;
- projectile trajectory prediction.

It has no browser UI, OpenCV GUI, camera device access, dataset management, or
training code.

### `src`

Owns tracked ROS2 interface integration:

- `src/interface/target_msgs`: imported external target interface messages;
- `src/interface/target_manager`: validates, filters, and rate-limits raw
  target predictions before planner/state-machine consumption;
- `src/tennisbot_vision_msgs`: repository-owned vision-side ROS messages;
- `src/tennisbot_interface_adapter`: event-driven bridge between vision-side
  topics and the imported external interface.

The nominal vision target and chassis-position paths are 30 Hz. The managed
target output remains at most 10 Hz by design.

### Target Headless ROS Runtime

The intended real runtime is a headless ROS vision node, not a frontend. The
target design is documented in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md).

The node should consume stereo camera frames and timestamped chassis pose,
transform triangulated ball points into the field/interface frame, fit the
trajectory, and publish `/vision/target_prediction`. The adapter then forwards
that data to `/target/raw`.

### `apps/live3d`

Owns the browser runtime/reference UI:

- opens two browser USB camera streams;
- loads YOLO and calibration artifacts from `/artifacts/...`;
- runs browser ONNX YOLO inference when a compatible package is present;
- overlays detections;
- feeds left/right detections to `packages/core`;
- renders the camera-frame 3D point, trail, prediction curve, and landing point;
- exposes `window.__tennisbotLive3dSnapshot` for local runtime inspection.

Current limitation: Live3D can load stereo calibration artifacts, but it does
not know the physical camera pose relative to a tennis court. Its 3D output
should be treated as camera-frame geometry until a court/world transform is
measured and applied. It is not the target real closed-loop runtime.

## Runtime Flow

```text
1. tools/calibration captures mono/stereo ChArUco sessions
2. tools/calibration solves mono/stereo calibration packages under artifacts/calibration/...
3. tools/yolo creates or verifies artifacts/models/tennis_ball_yolo
4. tools/stereo can run the local OpenCV 4K stereo coordinate GUI
5. the future headless ROS vision node reads two camera streams
6. the node runs YOLO, stereo pairing, triangulation, field-frame transforms,
   and trajectory prediction
7. the node publishes `/vision/target_prediction`
8. `tennisbot_interface_adapter` forwards to `/target/raw`
9. `target_manager` publishes `/target/managed` for the planner/state machine
```

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
by average focal length. The remaining physical gap is court/world pose: current
3D output is in the left camera frame.

Live3D exposes browser readiness gates for local reference operation, but the
remaining runtime gap is the headless ROS vision node described in
[Headless ROS Vision Runtime Target](headless_ros_vision_runtime.md).

## Main Commands

Camera brightness sanity check:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
bun scripts/calib.ts preview
```

Start the local browser runtime:

```bash
bun scripts/live3d.ts
bun scripts/live3d.ts --status
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

Verify Live3D:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

## Remaining Engineering Work

- Recalibrate after the cameras are mounted in their real physical positions.
- Add timestamped chassis pose with yaw for chassis-mounted cameras.
- Add configured `T_chassis_camera` extrinsics.
- Build the headless ROS vision node that publishes `/vision/target_prediction`.
- Verify `/vision/target_prediction` -> `/target/raw` -> `/target/managed`
  with ROS/Gazebo or real chassis pose and control links.
