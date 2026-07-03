# TennisBot

Local-machine-first workspace for the TennisBot stereo vision runtime.

The active repository code lives in top-level `packages/`, `scripts/`, `src/`,
and `tools/`. Local legacy lab code can exist under ignored
`desperate/` when present, but it is outside the active runtime path.
Calibration capture is handled by the mainline `tools/calibration` OpenCV
workflow.

## Projects

| Project | Purpose |
| --- | --- |
| `packages/contracts` | Shared TypeScript data contracts |
| `packages/core` | Artifact validation, stereo pairing, triangulation helpers |
| `src` | ROS2 target interface, optional vision adapter, and headless vision runtime packages |
| `tools/calibration` | Fixed DFOptix ChArUco OpenCV mono/stereo capture GUI |
| `tools/yolo` | Standalone YOLO runtime model package tooling |
| `tools/stereo` | Local OpenCV stereo recorder, coordinate GUI, and replay tooling |
| `artifacts/` | Ignored local runtime outputs for calibration and model packages |
| `desperate/` | Ignored local-only archive for legacy lab code, not part of the parent Git repository |

## Common Commands

Build the ROS interface and headless vision packages:

```bash
source /opt/ros/humble/setup.bash
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select \
  target_manager tennisbot_headless_vision \
  --symlink-install --allow-overriding target_manager
source install/setup.bash
```

Start the headless vision runtime and target manager in separate terminals after
the workspace is sourced:

```bash
ros2 launch tennisbot_headless_vision headless_vision.launch.py
ros2 launch target_manager target_manager.launch.py
```

Inspect the runtime topics:

```bash
ros2 topic list -t
ros2 topic echo /robot/chassis_state
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

Run camera checks and calibration:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

Calibration and YOLO annotation/package commands do not require Torch, CUDA, or
Ultralytics. Keep the default `uv sync` path for `tools/calibration` and
`tools/yolo`; only pure YOLO camera detection uses `uv run --extra detect ...`.

Start the YOLO annotation frontend/backend:

```bash
bun scripts/yolo.ts annotate
```

Create dry-run YOLO artifacts:

```bash
cd tools/yolo
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Create a runtime YOLO package from existing local model files:

```bash
cd tools/yolo
uv run tennisbot-yolo package create \
  --output-dir ../../artifacts/models/tennis_ball_yolo \
  --model-pt ../../artifacts/model_candidates/finetune_indoor_cam1/best.pt \
  --model-onnx ../../artifacts/model_candidates/finetune_indoor_cam1/best.onnx \
  --default-model onnx \
  --eval-report ../../artifacts/model_candidates/finetune_indoor_cam1/eval_report.md \
  --eval-metrics ../../artifacts/model_candidates/finetune_indoor_cam1/eval_metrics.json
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

## Architecture

- [Current architecture](docs/current/architecture.md)
- [Headless ROS vision runtime target](docs/current/headless_ros_vision_runtime.md)
- [Current status](docs/current/status.md)
- [Command usage](docs/current/command_usage.md)
- [Operator runbook](docs/current/operator_runbook.md)
- [Camera devices](docs/current/camera_devices.md)

## Git Workflow

For active code in `packages/`, `scripts/`, `src/`, `tools/`, and
`docs/`, commit directly in this repository.

Legacy lab code under `desperate/` is ignored local reference material. Do not
commit it from the parent repository; migrate needed behavior into `packages/`,
`src/`, or `tools/` with focused tests and documentation.

## Remote Status

The parent repository no longer tracks submodules. Local legacy code under
`desperate/` may still have historical upstream origins, but that code is
ignored and outside the active runtime path.
