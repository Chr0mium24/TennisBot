# TennisBot Current Architecture

Date: 2026-06-29

## Current Shape

TennisBot is now a local-machine-first workspace. The active runtime code lives
in top-level `apps/`, `packages/`, and `tools/`; older lab directories remain
as legacy/reference submodules and are not the runtime boundary.

```text
TennisBot/
  apps/
    live3d/          browser USB stereo camera, YOLO inference, runtime 3D UI

  packages/
    contracts/       shared TypeScript data contracts
    core/            stereo pairing, triangulation, prediction, artifact loaders

  tools/
    calibration/     standalone calibration package tool
    yolo/            standalone YOLO model package tool

  artifacts/         ignored local runtime artifacts
    calibration/
    models/

  docs/              plans, results, reviews, runbooks
```

Legacy/reference submodules still present:

```text
CameraCalibLab/
TennisBallDetectorLab/
BallTrajectoryLab/
TennisWebSim/
TennisBotCV/
```

They are not used as the main runtime architecture. `TennisBallDetectorLab`
currently has user-owned dirty state and remains untouched.

## Boundaries

### `tools/yolo`

Owns YOLO package production and verification. It does not own Live3D runtime
state, stereo geometry, prediction, camera UI, or calibration.

Default runtime output:

```text
artifacts/models/tennis_ball_yolo/
```

### `tools/calibration`

Owns mono/stereo calibration package production and verification. It does not
own YOLO inference, trajectory prediction, or Live3D rendering. It can import
existing CameraCalibLab calibration JSON into the runtime artifact contract
without making the main runtime depend on CameraCalibLab source code.

Default runtime output:

```text
artifacts/calibration/stereo_cam1_cam2/
```

### `packages/core`

Owns pure runtime algorithms and artifact metadata validation:

- YOLO and stereo calibration artifact metadata loaders;
- stereo detection pairing;
- rectified stereo triangulation;
- projectile trajectory prediction.

It has no YOLO training, calibration GUI, browser rendering, or device-specific
board code.

### `apps/live3d`

Owns the real-machine UI:

- opens two browser USB camera streams by explicit Start/Stop controls;
- loads YOLO and calibration artifact packages from `/artifacts/...`;
- uses `onnxruntime-web` for browser ONNX YOLO inference when a valid ONNX
  package is available;
- overlays runtime detections on both camera views;
- feeds left/right detections to `packages/core`;
- renders runtime 3D ball point, trail, prediction curve, and landing point;
- falls back to explicitly labelled fixture views when real runtime state is not
  available.

## Runtime Flow

```text
1. tools/calibration mono cam1
2. tools/calibration mono cam2
3. tools/calibration stereo
4. tools/yolo package create/verify
5. apps/live3d loads /artifacts/models/tennis_ball_yolo
6. apps/live3d loads /artifacts/calibration/stereo_cam1_cam2
7. user starts two USB cameras in the browser
8. user starts YOLO backend
9. Live3D runs ONNX inference on left/right frames
10. Live3D selects stereo pair, triangulates 3D point, updates prediction
```

## Main Commands

Run Live3D:

```bash
cd apps/live3d
bun install
bun run dev
```

Verify Live3D:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

Create dry-run calibration artifacts:

```bash
cd tools/calibration
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Import existing CameraCalibLab calibration:

```bash
cd tools/calibration
uv run tennisbot-calibration package import-camera-calib-lab \
  --cam1 ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/cam1_mono/calibration/calibration.json \
  --cam2 ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/cam2_mono/calibration/calibration.json \
  --stereo ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/stereo/calibration/calibration.json \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --source-session CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Create dry-run YOLO artifacts:

```bash
cd tools/yolo
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Create runtime YOLO artifacts from existing local model files:

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

Verify packages:

```bash
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
```

## Current Verification Evidence

Most recent software verification after Wave 11:

```text
cd apps/live3d && bun test
Result: 38 passing tests, 0 failures.

cd apps/live3d && bun run typecheck
Result: passed.

cd apps/live3d && bun run build
Result: passed.
```

The software path is connected through Live3D, ONNX backend boundary, core
stereo triangulation, and prediction using synthetic tests.

Runtime artifacts have also been imported locally:

```text
YOLO: dry_run=false, inference_ready=true, default_model=onnx.
YOLO static smoke: 109/109 matched labeled samples detected at threshold 0.05.
Calibration: dry_run=false, hardware_validated=true, package verify accepted.
Calibration quality warning: stereo_rms=23.487 px, epipolar_rms=30.802 px,
rectification_y_p95=19.304 px.
```

## Remaining Physical Validation

The architecture is implemented in software. These items still require real
hardware validation:

- run Live3D with two real USB cameras in the target browser;
- verify ONNX detections on live frames;
- verify runtime 3D point stability and prediction quality;
- re-run mono/stereo calibration if imported stereo error remains high;
- validate ROS/Gazebo closed-loop catch behavior only after the real visual
  tracking path is stable.
