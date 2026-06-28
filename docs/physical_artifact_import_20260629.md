# Physical Artifact Import

Date: 2026-06-29

## Scope

This records importing existing local-machine assets into the simplified
TennisBot runtime artifact layout.

Imported assets:

- YOLO model package rebuilt from
  `TennisBallDetectorLab/yolo/runs/training/finetune_indoor_cam1/weights/best.pt`
  and an exported ONNX model under `artifacts/model_candidates/`.
- Stereo calibration package from `CameraCalibLab/calibration_packages/`.

Runtime output paths:

```text
artifacts/models/tennis_ball_yolo/
artifacts/calibration/stereo_cam1_cam2/
```

## YOLO Package

Command:

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

Result:

```text
dry_run: false
inference_ready: true
default_model: onnx
model.pt: 5,450,181 bytes
model.onnx: 10,261,007 bytes
static_smoke detected_at_threshold: 109 / 109
```

## Calibration Package

Command:

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

Result:

```text
accepted: true
dry_run: false
hardware_validated: true
runtime_quality_warning: true
baseline_m: 0.06778794228688073
accepted_pair_count: 33
stereo_rms_reprojection_px: 23.486769410254507
epipolar_rms_px: 30.801563164769544
rectification_y_p95_px: 19.30416870117187
```

The source calibration is real hardware output, but the stereo quality metrics
are too high for final physical accuracy claims. This package is acceptable for
Live3D artifact loading and runtime smoke testing. It should not be treated as
the final calibration for 3D prediction quality.

## Verification

Commands:

```bash
cd tools/calibration
uv run pytest -q
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Result:

```text
9 tests passed.
Calibration package verification accepted with no missing files.
```

## Remaining Physical Gates

- Open Live3D in the browser and grant access to the two real USB cameras.
- Confirm the ONNX model detects tennis balls on live frames.
- Confirm the imported calibration produces stable 3D points.
- Re-run mono and stereo calibration if the imported stereo error remains high.
