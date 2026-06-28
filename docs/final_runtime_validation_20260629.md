# TennisBot Final Runtime Validation

Date: 2026-06-29

## Scope

This validation covers the current local-machine software architecture:

- `packages/contracts`
- `packages/core`
- `tools/calibration`
- `tools/yolo`
- `apps/live3d`

It does not claim ROS/Gazebo catch control or final physical 3D accuracy. A
real local YOLO package and an imported real calibration package are available
for runtime smoke testing. Live3D has also opened two real USB cameras in
Chrome and run the ONNX backend on live frames, but the current scene did not
contain a detectable tennis ball and the imported stereo calibration has quality
warnings.

Follow-up YOLO static validation found that Live3D was decoding the exported
ONNX `xyxy_pixels` output as `xywh`. That postprocessing bug is fixed. The
initial `detector_package` model failed the static quality check, so the local
runtime package was rebuilt from
`TennisBallDetectorLab/yolo/runs/training/finetune_indoor_cam1/weights/best.pt`
and an exported ONNX model. The rebuilt package detects 109/109 matched labeled
samples at `confidence_threshold: 0.05`.

## Verified Commands

### Contracts

```bash
cd packages/contracts
bun test
bun run typecheck
```

Result: 4 tests passed, typecheck passed.

### Core

```bash
cd packages/core
bun test
bun run typecheck
```

Result: 21 tests passed, typecheck passed.

### Live3D

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

Result: 40 tests passed, typecheck passed, browser bundle built.

Dev server smoke:

```bash
PORT=5178 bun ./scripts/serve.js
curl -I http://localhost:5178/
curl -I http://localhost:5178/assets/main.js
curl -I http://localhost:5178/artifacts/models/tennis_ball_yolo/package.json
curl -I http://localhost:5178/artifacts/calibration/stereo_cam1_cam2/package.json
```

Result: all HTTP checks returned `200 OK`.

Hardware smoke:

```bash
v4l2-ctl --list-devices
ffmpeg ... -i /dev/video0 ... -i /dev/video2 ...
google-chrome --headless=new --use-fake-ui-for-media-stream ...
```

Result: two `USU Camera 4K` devices were enumerated, `/dev/video0` and
`/dev/video2` were opened simultaneously, Chrome opened distinct left/right
`MediaStream` tracks at 1280x720, and the ONNX backend ran continuously against
live camera frames without ONNX session errors. The frames produced zero
tennis-ball detections in the current scene, so runtime 3D remained waiting for
a detection.

### Calibration Tool

```bash
cd tools/calibration
uv run pytest -q
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
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

Result: 9 tests passed. Dry-run mono and stereo package generation still works.
The existing CameraCalibLab stereo output was also imported into
`artifacts/calibration/stereo_cam1_cam2` and verified with `accepted: true`,
`dry_run: false`, and `hardware_validated: true`.

Imported calibration quality warning:

```text
stereo_rms_reprojection_px: 23.486769410254507
epipolar_rms_px: 30.801563164769544
rectification_y_p95_px: 19.30416870117187
```

### YOLO Tool

```bash
cd tools/yolo
uv run pytest -q
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package create \
  --output-dir ../../artifacts/models/tennis_ball_yolo \
  --model-pt ../../artifacts/model_candidates/finetune_indoor_cam1/best.pt \
  --model-onnx ../../artifacts/model_candidates/finetune_indoor_cam1/best.onnx \
  --default-model onnx \
  --eval-report ../../artifacts/model_candidates/finetune_indoor_cam1/eval_report.md \
  --eval-metrics ../../artifacts/model_candidates/finetune_indoor_cam1/eval_metrics.json
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Result: 13 tests passed. A real runtime YOLO package was written from the
`finetune_indoor_cam1` best model and verified with `dry_run: false`,
`inference_ready: true`, `default_model: onnx`, and static smoke
`detected_at_threshold: 109 / 109`.

## Current Evidence

- YOLO and calibration are separate standalone tool packages under `tools/`.
- Live3D consumes only model/calibration artifacts under `artifacts/`.
- Runtime core algorithms live under `packages/core`.
- Shared data contracts live under `packages/contracts`.
- `artifacts/models/tennis_ball_yolo` now contains a real ONNX-default package
  rebuilt from `finetune_indoor_cam1/weights/best.pt`.
- `artifacts/calibration/stereo_cam1_cam2` now contains a real imported stereo
  package with explicit runtime quality warnings.
- Live3D opened two real USB cameras in Chrome and ran the ONNX backend on live
  browser frames without session concurrency errors.
- Live3D now decodes the current ONNX package's `xyxy_pixels` output correctly.
- The current YOLO model package passed the static detection-quality smoke at
  `confidence_threshold: 0.05` on 109 matched labeled images.
- Board-side runtime code is not part of the current active architecture.
- The only dirty worktree entry after validation is the pre-existing
  `TennisBallDetectorLab` submodule state, which remains untouched.

## Remaining Physical Validation

Before claiming full real-world operation:

1. Put a tennis ball in both USB camera views and confirm nonzero runtime
   detections.
2. Confirm runtime 3D scene, prediction curve, and landing marker update from
   those detections.
3. Re-run mono/stereo calibration if imported stereo quality remains poor.
4. Validate ROS/Gazebo closed-loop catch behavior only after real visual
   tracking is stable.
