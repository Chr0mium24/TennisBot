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
| `packages/vision-python` | Shared camera identities, controls, YOLO and stereo runtime algorithms |
| `src` | Vision runtime package; target interfaces are provided by the external control workspace |
| `tools/calibration` | Fixed DFOptix ChArUco OpenCV mono/stereo capture GUI |
| `tools/recording` | V4L2/ffmpeg camera recording CLI migrated from local lab scripts |
| `tools/yolo` | Standalone YOLO runtime model package tooling |
| `artifacts/` | Ignored local runtime outputs for calibration and model packages |
| `desperate/` | Ignored local-only archive for legacy lab code, not part of the parent Git repository |

## Common Commands

Build the local vision runtime package after sourcing ROS and the control
workspace that provides `target_msgs` and `target_manager`:

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
source install/setup.bash
```

Start the vision runtime and the external target manager in separate
terminals after both workspaces are sourced:

```bash
ros2 launch tennisbot_vision_runtime vision_runtime.launch.py
ros2 launch target_manager target_manager.launch.py
```

Or use the uv/Python runtime launcher. It auto-sources ROS, the control workspace,
and this repository's `install/setup.bash` before starting ROS child
processes:

```bash
uv run scripts/vision-runtime.py run
uv run scripts/vision-runtime.py run --record --session test01 --tile
uv run scripts/vision-runtime.py task --task-id 42 --session catch42 --tile
```

Inspect the runtime topics:

```bash
ros2 topic list -t
ros2 interface show target_msgs/msg/ChassisPosition
ros2 topic echo /robot/chassis_position
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

Run camera checks and calibration:

```bash
uv run scripts/camera.py list
uv run scripts/camera.py check
uv run scripts/camera.py preview stereo
uv run scripts/calib.py online mono cam1
uv run scripts/calib.py online mono cam2
uv run scripts/calib.py online stereo
```

Record raw camera video through the config-driven ffmpeg recorder:

```bash
uv run scripts/record.py mono cam1 --dry-run
uv run scripts/record.py stereo --duration 60
uv run scripts/record.py stereo --gui
```

Run online vision diagnostics, optionally recording the already-open streams:

```bash
uv run scripts/test.py yolo mono cam1
uv run scripts/test.py yolo stereo --gui --record
uv run scripts/test.py triangulation stereo --json
uv run scripts/test.py communication chassis-position
```

The calibration wrapper writes timestamped package directories by default so a
new run does not overwrite the previous result. Use `--output` only when
intentionally writing a fixed runtime path.

Calibration and YOLO annotation/package commands do not require Torch, CUDA, or
Ultralytics. Keep the default `uv sync` path for `tools/calibration` and
`tools/yolo`; inference defaults to the CPU-only `detect` extra. Pass `--cuda`
to `scripts/yolo.py` or `scripts/test.py` only on an NVIDIA CUDA 13.0 host.

Start the YOLO annotation frontend/backend:

```bash
uv run scripts/yolo.py annotate
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
- [Vision Runtime](docs/current/vision_runtime.md)
- [Current status](docs/current/status.md)
- [Chinese run guide](docs/current/how_to_run_zh.md)
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
