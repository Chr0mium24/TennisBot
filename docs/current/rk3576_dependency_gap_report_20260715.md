# RK3576 Dependency and Gap Report

Date: 2026-07-15

## Scope

This report covers the active repository paths:

- `src/tennisbot_vision_runtime`
- `scripts`
- `tools/calibration`
- `tools/recording`
- `tools/stereo`
- `tools/yolo`
- `packages/contracts`
- `packages/core`

`desperate/` is treated as legacy local reference code and is not part of the
runtime deployment target.

## Direct Project Dependencies

### ROS Runtime

`src/tennisbot_vision_runtime` is an `ament_python` ROS 2 package.

ROS package dependencies:

- `ament_python`
- `ament_index_python`
- `builtin_interfaces`
- `launch`
- `launch_ros`
- `rclpy`
- external `target_msgs`

External workspace dependencies:

- `target_msgs`
- `target_manager`
- current launcher assumes the control workspace setup file at
  `~/tennis_robot_ws/install/setup.bash`, unless overridden by environment
  variables or `--setup-file`.

Runtime Python imports beyond ROS:

- `cv2`
- `numpy`
- `ultralytics`
- local `tennisbot_stereo` modules from `tools/stereo/src`

System commands used by the runtime wrapper:

- `ros2`
- `bash`
- `v4l2-ctl`

### Python Tools

All maintained Python tools are `uv` projects and declare `requires-python =
">=3.12"`.

| Path | Purpose | Direct dependencies | Optional dependencies |
|---|---|---|---|
| `tools/calibration` | ChArUco mono/stereo calibration and camera preview | `numpy`, `opencv-python`, `pyyaml` | `pytest` for dev |
| `tools/recording` | V4L2/ffmpeg recording CLI and GUI | `pyyaml` | `pytest` for dev |
| `tools/stereo` | Local stereo camera GUI, YOLO detection, matching, triangulation | `numpy`, `opencv-python` | `ultralytics` via `detect`, plus its `torch`/`torchvision` stack |
| `tools/yolo` | annotation, model packaging, ONNX helper inference, augmentation, detect tools | `fastapi`, `numpy`, `onnxruntime`, `pillow`, `pydantic`, `uvicorn` | `opencv-python` via `augment`; `opencv-python` and `ultralytics` via `detect` |

System commands used by tools:

- `v4l2-ctl`
- `ffmpeg`
- `ffplay`
- OpenCV GUI display support
- `tkinter` for the recording GUI

### TypeScript and Bun Tools

| Path | Purpose | Dependencies |
|---|---|---|
| `packages/contracts` | Shared TypeScript data contracts | `typescript` |
| `packages/core` | Artifact validation and stereo geometry helpers | `typescript` |
| `tools/stereo/web/replay` | Stereo replay frontend | `three`, `typescript`, `@types/bun`, `@types/three` |
| `tools/yolo/web/yolo-annotator` | YOLO annotation frontend checks | `typescript` |
| `tools/yolo/web/yolo-sprite-review` | Sprite review frontend wrapper | no package dependency beyond Bun runtime |

Front-end tasks should use `bun`.

## Current Runtime Artifacts

Available now:

- Stereo calibration package:
  `artifacts/calibration/stereo_cam1_cam2`
- YOLO model package:
  `artifacts/models/tennis_ball_yolo`

Important artifact state:

- The calibration package is marked accepted and hardware validated for the
  stereo rig, with `baseline_m=0.1649889033601914`.
- The YOLO package currently ships `model.pt` only and has
  `default_model: "pt"`.
- The current main runtime loads the `.pt` model through
  `ultralytics.YOLO`, not RKNN.

## RK3576 Deployment Gaps

### 1. Board Operating System and ROS Strategy

The repo commands currently assume ROS 2 Humble:

```bash
source /opt/ros/humble/setup.bash
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
```

Before moving to RK3576, choose and validate:

- the board image, preferably a vendor Debian/Ubuntu image with working V4L2
  cameras and RKNPU driver support;
- ROS 2 distribution and Python version strategy;
- whether the ROS node will run in the ROS system Python, while data tools keep
  their separate Python 3.12 `uv` environments.

This matters because common ROS Humble deployments use Python 3.10, while the
tool projects declare Python 3.12 or newer.

### 2. NPU Inference Path

Current code is not RK3576 NPU ready. It uses:

```text
model.pt -> ultralytics -> torch
```

For RK3576 NPU deployment, add:

- export current YOLO checkpoint to ONNX;
- convert ONNX to `.rknn` with RKNN-Toolkit2 for target platform `rk3576`;
- prepare a representative quantization/calibration dataset;
- install board-side RKNN runtime, `librknnrt.so`, and any required
  `rknn_server` or Lite2 package from the board vendor SDK;
- add a runtime detector adapter that can replace `YoloBallDetector` with RKNN
  inference while preserving the same `BallDetection` output contract;
- benchmark full-frame search and ROI inference on the RK3576 board.

Without this work, the board would run the `.pt` model on CPU/PyTorch or an
unsupported acceleration path. That is unlikely to be the correct production
path for 4K stereo real-time vision.

Rockchip's official RKNN Toolkit2 repository lists RK3576 as a supported
platform and describes the split between Toolkit2 conversion, Lite2 Python API,
Runtime C/C++ API, and the RKNPU kernel driver. Firefly's RK3576 NPU guide also
documents converting non-RKNN models to RKNN and preparing `librknnrt.so` /
`rknn_server` on Linux. FriendlyELEC similarly lists RK3576 as an RKNN-supported
platform.

References:

- https://github.com/airockchip/rknn-toolkit2
- https://wiki.t-firefly.com/en/ROC-RK3576-PC/usage_npu.html
- https://wiki.friendlyelec.com/wiki/index.php/NPU

### 3. Python Wheel and Native Library Risk

Do not assume the existing lock files are directly portable to RK3576.

Risk areas:

- `ultralytics` pulls in a large `torch`/`torchvision` stack;
- current lock files include desktop GPU/NVIDIA transitive packages on the
  development machine;
- `opencv-python` wheels may not match the board's camera, display, codec, and
  V4L2 needs;
- `onnxruntime` on aarch64 may be CPU-only and is not the same as using the
  RK3576 NPU.

Recommended board approach:

- keep ROS runtime dependencies installed in the ROS Python environment;
- use system or vendor OpenCV if V4L2/GUI/codec support is better than PyPI
  wheels;
- use `uv sync` for non-ROS tools only after testing aarch64 wheel resolution;
- avoid installing the `detect` extra on board unless a CPU PyTorch fallback is
  explicitly needed for debugging.

### 4. Hardware and Runtime Configuration

Still missing for a real catch loop:

- fixed chassis-to-camera extrinsics measured on the final mounted chassis;
- `camera_translation_m` and `camera_rotation_rpy_rad` set in
  `vision_runtime.yaml`;
- `/robot/chassis_position` published with field-frame `x`, `y`, and `yaw`;
- all runtime timestamps aligned to the same ROS clock;
- validated `/target/raw -> target_manager -> /target/managed` chain;
- final camera device mapping, permissions, exposure, white balance, gain,
  focus, and USB bandwidth checks;
- measured left/right camera sync error on the board;
- board thermal, CPU governor, NPU frequency, and sustained FPS measurement.

The fallback `allow_missing_yaw` mode must remain diagnostic only. It should not
be used to claim real closed-loop catch validation.

### 5. Packaging and Operations

Deployment still needs:

- board-specific install notes or script;
- service or launch wrapper that does not hard-code local developer paths;
- documented environment variables:
  - `ROS_SETUP`
  - `TENNISBOT_CONTROL_SETUP`
  - `TENNISBOT_LOCAL_SETUP`
- log directory policy for `runs/vision-runtime`;
- health checks for camera open, model load, pose freshness, target publish
  rate, and target-manager output.

## Suggested RK3576 Bring-up Order

1. Bring up OS, SSH, camera devices, `v4l2-ctl`, `ffmpeg`, and stable
   `/dev/video*` mapping.
2. Install ROS 2 and build the external control workspace with `target_msgs`
   and `target_manager`.
3. Build `tennisbot_vision_runtime` and run with camera disabled to verify ROS
   topics and launch files.
4. Run calibration and recording checks on the board or confirm that existing
   calibration remains valid after final mounting.
5. Convert the current YOLO checkpoint to ONNX and then RKNN; validate accuracy
   against the existing benchmark set.
6. Implement RKNN detector adapter and benchmark full-frame search plus ROI
   tracking on the board.
7. Measure and configure chassis-to-camera extrinsics.
8. Verify `/robot/chassis_position` field-frame yaw and timestamp freshness.
9. Run logged real stereo prediction and inspect `observations.ndjson`,
   `detections.ndjson`, and `targets.ndjson`.
10. Only after the above, test `/target/raw -> /target/managed` with the real
    chassis backend.

## Bottom Line

The repo has enough software structure for an RK3576 port, but it is not yet a
drop-in board deployment.

The largest missing item is the inference backend: the active runtime is
Ultralytics `.pt`, while RK3576 production should use an RKNN model and RKNN
runtime adapter. The second largest missing item is hardware validation:
extrinsics, chassis yaw/timestamps, camera stability, and target-manager
closed-loop behavior must be measured on the final RK3576 setup.
