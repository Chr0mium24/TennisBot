# TennisBot

Local-machine-first workspace for the TennisBot stereo vision runtime.

The active architecture now lives in top-level `apps/`, `packages/`, and
`tools/`. Legacy lab directories remain as reference submodules, but the live
runtime consumes only exported artifacts from `artifacts/`.

## Projects

| Project | Purpose |
| --- | --- |
| `apps/live3d` | Browser USB stereo camera UI, ONNX YOLO inference, runtime 3D visualization |
| `packages/contracts` | Shared TypeScript data contracts |
| `packages/core` | Artifact validation, stereo pairing, triangulation, trajectory prediction |
| `tools/calibration` | Standalone mono/stereo calibration package tooling |
| `tools/yolo` | Standalone YOLO runtime model package tooling |
| `artifacts/` | Ignored local runtime outputs for calibration and model packages |
| Legacy submodules | `CameraCalibLab`, `TennisBallDetectorLab`, `BallTrajectoryLab`, `TennisWebSim`, `TennisBotCV` are reference/history only for the current runtime path |

## Common Commands

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

Import existing CameraCalibLab calibration into runtime artifacts:

```bash
cd tools/calibration
uv run tennisbot-calibration package import-camera-calib-lab \
  --cam1 ../../CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7/calibration.json \
  --cam2 ../../CameraCalibLab/runs/calibrations/dfoptix_charuco_auto_cam2/calibration.json \
  --stereo ../../CameraCalibLab/runs/calibrations/dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622/calibration.json \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --source-session CameraCalibLab/runs/calibrations/dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
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

- [Current architecture](docs/current_architecture_20260629.md)
- [Final runtime validation](docs/final_runtime_validation_20260629.md)
- [Physical artifact import](docs/physical_artifact_import_20260629.md)
- [Live3D hardware smoke](docs/live3d_hardware_smoke_20260629.md)
- [YOLO static sample validation](docs/yolo_static_sample_validation_20260629.md)
- [Architecture simplification plan](docs/architecture_simplification_plan_20260628.md)
- [Multi-agent refactor task plan](docs/multi_agent_refactor_tasks_20260628.md)
- [Multi-agent refactor Wave 1 result](docs/multi_agent_refactor_wave1_result_20260628.md)
- [Multi-agent refactor Wave 2 core migration plan](docs/multi_agent_refactor_wave2_core_migration_plan_20260628.md)
- [Multi-agent refactor Wave 2 core migration result](docs/multi_agent_refactor_wave2_core_migration_result_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture plan](docs/multi_agent_refactor_wave3_live3d_core_fixture_plan_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture result](docs/multi_agent_refactor_wave3_live3d_core_fixture_result_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture review](docs/multi_agent_refactor_wave3_live3d_core_fixture_review_20260628.md)
- [Multi-agent refactor Wave 4 artifact loaders plan](docs/multi_agent_refactor_wave4_artifact_loaders_plan_20260628.md)
- [Multi-agent refactor Wave 4 artifact loaders result](docs/multi_agent_refactor_wave4_artifact_loaders_result_20260628.md)
- [Multi-agent refactor Wave 4 artifact loaders review](docs/multi_agent_refactor_wave4_artifact_loaders_review_20260628.md)
- [Multi-agent refactor Wave 5 calibration tool plan](docs/multi_agent_refactor_wave5_calibration_tool_plan_20260629.md)
- [Multi-agent refactor Wave 5 calibration tool result](docs/multi_agent_refactor_wave5_calibration_tool_result_20260629.md)
- [Multi-agent refactor Wave 5 calibration tool review](docs/multi_agent_refactor_wave5_calibration_tool_review_20260629.md)
- [Multi-agent refactor Wave 6 YOLO tool plan](docs/multi_agent_refactor_wave6_yolo_tool_plan_20260629.md)
- [Multi-agent refactor Wave 6 YOLO tool result](docs/multi_agent_refactor_wave6_yolo_tool_result_20260629.md)
- [Multi-agent refactor Wave 6 YOLO tool review](docs/multi_agent_refactor_wave6_yolo_tool_review_20260629.md)
- [Multi-agent refactor Wave 7 Live3D artifacts plan](docs/multi_agent_refactor_wave7_live3d_artifacts_plan_20260629.md)
- [Multi-agent refactor Wave 7 Live3D artifacts result](docs/multi_agent_refactor_wave7_live3d_artifacts_result_20260629.md)
- [Multi-agent refactor Wave 7 Live3D artifacts review](docs/multi_agent_refactor_wave7_live3d_artifacts_review_20260629.md)
- [Multi-agent refactor Wave 8 Live3D USB camera plan](docs/multi_agent_refactor_wave8_live3d_usb_camera_plan_20260629.md)
- [Multi-agent refactor Wave 8 Live3D USB camera result](docs/multi_agent_refactor_wave8_live3d_usb_camera_result_20260629.md)
- [Multi-agent refactor Wave 8 Live3D USB camera review](docs/multi_agent_refactor_wave8_live3d_usb_camera_review_20260629.md)
- [Multi-agent refactor Wave 9 Live3D YOLO inference plan](docs/multi_agent_refactor_wave9_live3d_yolo_inference_plan_20260629.md)
- [Multi-agent refactor Wave 9 Live3D YOLO inference result](docs/multi_agent_refactor_wave9_live3d_yolo_inference_result_20260629.md)
- [Multi-agent refactor Wave 9 Live3D YOLO inference review](docs/multi_agent_refactor_wave9_live3d_yolo_inference_review_20260629.md)
- [Multi-agent refactor Wave 10 Live3D ONNX backend plan](docs/multi_agent_refactor_wave10_live3d_onnx_backend_plan_20260629.md)
- [Multi-agent refactor Wave 10 Live3D ONNX backend result](docs/multi_agent_refactor_wave10_live3d_onnx_backend_result_20260629.md)
- [Multi-agent refactor Wave 10 Live3D ONNX backend review](docs/multi_agent_refactor_wave10_live3d_onnx_backend_review_20260629.md)
- [Multi-agent refactor Wave 11 Live3D runtime 3D plan](docs/multi_agent_refactor_wave11_live3d_runtime_3d_plan_20260629.md)
- [Multi-agent refactor Wave 11 Live3D runtime 3D result](docs/multi_agent_refactor_wave11_live3d_runtime_3d_result_20260629.md)
- [Multi-agent refactor Wave 11 Live3D runtime 3D review](docs/multi_agent_refactor_wave11_live3d_runtime_3d_review_20260629.md)

## Git Workflow

For active code in `apps/`, `packages/`, `tools/`, and `docs/`, commit directly
in this repository.

Legacy submodule edits are out of scope for the current runtime path. If a
legacy submodule must be changed, commit inside that submodule first, then
commit the updated gitlink from the top-level repository.

```bash
git -C <legacy-submodule> status
git -C <legacy-submodule> commit -am "..."
git add <legacy-submodule>
git commit -m "Update legacy submodule pointer"
```

## Remote Status

The historical submodules use GitHub remotes under `Chr0mium24`. The current
runtime path does not depend on board-side deployment code.
