# TennisBot Final Runtime Validation

Date: 2026-06-29

## Scope

This validation covers the current local-machine software architecture:

- `packages/contracts`
- `packages/core`
- `tools/calibration`
- `tools/yolo`
- `apps/live3d`

It does not claim physical validation with real USB cameras or ROS/Gazebo catch
control. A real local YOLO package and an imported real calibration package are
available for runtime smoke testing, but the imported stereo calibration has
quality warnings and must be revalidated before final 3D accuracy claims.

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

Result: 38 tests passed, typecheck passed, browser bundle built.

Dev server smoke:

```bash
PORT=5178 bun ./scripts/serve.js
curl -I http://localhost:5178/
curl -I http://localhost:5178/assets/main.js
curl -I http://localhost:5178/artifacts/models/tennis_ball_yolo/package.json
curl -I http://localhost:5178/artifacts/calibration/stereo_cam1_cam2/package.json
```

Result: all HTTP checks returned `200 OK`.

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
  --model-pt ../../TennisBallDetectorLab/detector_package/model.pt \
  --model-onnx ../../TennisBallDetectorLab/detector_package/model.onnx \
  --model-rknn ../../TennisBallDetectorLab/detector_package/model.rknn \
  --default-model onnx
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Result: 12 tests passed. A real runtime YOLO package was written from
`TennisBallDetectorLab/detector_package/` and verified with `dry_run: false`,
`inference_ready: true`, and `default_model: onnx`.

## Current Evidence

- YOLO and calibration are separate standalone tool packages under `tools/`.
- Live3D consumes only model/calibration artifacts under `artifacts/`.
- Runtime core algorithms live under `packages/core`.
- Shared data contracts live under `packages/contracts`.
- `artifacts/models/tennis_ball_yolo` now contains a real ONNX-default package.
- `artifacts/calibration/stereo_cam1_cam2` now contains a real imported stereo
  package with explicit runtime quality warnings.
- Board-side runtime code is not part of the current active architecture.
- The only dirty worktree entry after validation is the pre-existing
  `TennisBallDetectorLab` submodule state, which remains untouched.

## Remaining Physical Validation

Before claiming full real-world operation:

1. Run Live3D against two physical USB cameras.
2. Confirm browser ONNX detections on real camera frames.
3. Confirm stereo 3D point stability and prediction quality.
4. Re-run mono/stereo calibration if imported stereo quality remains poor.
5. Validate ROS/Gazebo closed-loop catch behavior only after real visual
   tracking is stable.
