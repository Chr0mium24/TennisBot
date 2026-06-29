# TennisBot

Local-machine-first workspace for the TennisBot stereo vision runtime.

The active architecture now lives in top-level `apps/`, `packages/`, and
`tools/`. Legacy lab code is local-only reference material under ignored
`desperate/` when present; the live runtime consumes only exported artifacts
from `artifacts/`.

## Projects

| Project | Purpose |
| --- | --- |
| `apps/live3d` | Browser USB stereo camera UI, ONNX YOLO inference, runtime 3D visualization |
| `packages/contracts` | Shared TypeScript data contracts |
| `packages/core` | Artifact validation, stereo pairing, triangulation, trajectory prediction |
| `tools/calibration` | Standalone mono/stereo calibration package tooling |
| `tools/yolo` | Standalone YOLO runtime model package tooling |
| `artifacts/` | Ignored local runtime outputs for calibration and model packages |
| `desperate/` | Ignored local-only archive for legacy lab code, not part of the parent Git repository |

## Common Commands

Start the local operator surfaces:

```bash
bun scripts/start-local-runtime.ts
```

Check whether they are already serving:

```bash
bun scripts/start-local-runtime.ts --status
```

Run the local preflight:

```bash
bun scripts/operator-preflight.ts --output docs/local_runtime_preflight_YYYYMMDD.md
```

Check physical acceptance status:

```bash
bun scripts/physical-validation-status.ts --output docs/local_physical_validation_status_YYYYMMDD.md
```

Record the printed target measurement:

```bash
cd tools/calibration
uv run tennisbot-calibration target record-print-check --measured-square-mm 15.0
```

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

Run the original OpenCV stereo calibration GUI:

```bash
cd desperate/CameraCalibLab
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --config configs/dfoptix_charuco_15mm_capture.yaml \
  --output captures/local/dfoptix_stereo_charuco_auto_session \
  --calibration-output runs/calibrations/dfoptix_stereo_charuco_auto \
  --views 30 \
  --left-device /dev/video0 \
  --right-device /dev/video2
```

Create dry-run calibration artifacts:

```bash
cd tools/calibration
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Capture calibration sessions from local USB cameras:

```bash
cd tools/calibration
uv run tennisbot-calibration capture mono \
  --camera-id cam1 \
  --device /dev/video0 \
  --output ../../artifacts/calibration_sessions/cam1_session
uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/stereo_session \
  --prepare-uvc-controls
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/stereo_session \
  --output-report ../../docs/calibration_capture_quality_YYYYMMDD.md
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/stereo_session \
  --output ../../artifacts/calibration_sessions/stereo_session/observations.json \
  --output-report ../../docs/calibration_charuco_detection_YYYYMMDD.md
uv run tennisbot-calibration calibrate mono \
  --observations ../../artifacts/calibration_sessions/cam1_session/observations.json \
  --output ../../artifacts/calibration/cam1 \
  --camera-id cam1
uv run tennisbot-calibration calibrate stereo \
  --observations ../../artifacts/calibration_sessions/stereo_session/observations.json \
  --left-mono ../../artifacts/calibration/cam1 \
  --right-mono ../../artifacts/calibration/cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2
```

Import existing CameraCalibLab calibration into runtime artifacts:

```bash
cd tools/calibration
uv run tennisbot-calibration package import-scanned-camera-calib-lab \
  --root ../../desperate/CameraCalibLab/runs/calibrations \
  --cam1-pattern dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7 \
  --cam2-pattern dfoptix_charuco_auto_cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --limit 12 \
  --output-report ../../docs/calibration_candidate_scan_YYYYMMDD.md
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
- [Current status](docs/current_status_20260629.md)
- [Desperate legacy code retirement](docs/desperate_legacy_code_retirement_20260629.md)
- [Local physical validation checklist](docs/local_physical_validation_checklist_20260629.md)
- [Local physical validation status script](docs/local_physical_validation_status_script_20260629.md)
- [Target print check recorder](docs/target_print_check_recorder_20260629.md)
- [Final runtime validation](docs/final_runtime_validation_20260629.md)
- [Local runtime operator runbook](docs/local_runtime_operator_runbook_20260629.md)
- [Local runtime launcher next action](docs/local_runtime_launcher_next_action_20260629.md)
- [Local runtime preflight](docs/local_runtime_preflight_20260629.md)
- [Local physical validation status](docs/local_physical_validation_status_20260629.md)
- [Physical artifact import](docs/physical_artifact_import_20260629.md)
- [Calibration candidate scan](docs/calibration_candidate_scan_20260629.md)
- [Calibration capture session flow](docs/calibration_capture_session_flow_20260629.md)
- [Calibration capture quality dry run](docs/calibration_capture_quality_20260629.md)
- [Calibration capture quality hardware probe](docs/calibration_capture_quality_hardware_probe_20260629.md)
- [Calibration ChArUco detection dry run](docs/calibration_charuco_detection_20260629.md)
- [Calibration ChArUco detection hardware probe](docs/calibration_charuco_detection_hardware_probe_20260629.md)
- [Calibration ChArUco target sheet](docs/calibration_charuco_target_sheet_20260629.md)
- [Calibration mono solve](docs/calibration_mono_solve_20260629.md)
- [Calibration mono solve capture quality](docs/calibration_mono_solve_capture_quality_20260629.md)
- [Calibration mono solve ChArUco detection](docs/calibration_charuco_detection_mono_solve_20260629.md)
- [Calibration stereo solve](docs/calibration_stereo_solve_20260629.md)
- [Calibration stereo solve capture quality](docs/calibration_stereo_solve_capture_quality_20260629.md)
- [Calibration stereo solve ChArUco detection](docs/calibration_charuco_detection_stereo_solve_20260629.md)
- [Calibration frontend review revert](docs/calibration_frontend_review_revert_20260629.md)
- [Tool boundary audit](docs/tool_boundary_audit_20260629.md)
- [Legacy board/runtime shell retirement](docs/legacy_board_retirement_20260629.md)
- [Live3D hardware smoke](docs/live3d_hardware_smoke_20260629.md)
- [Live3D hardware acceptance checklist](docs/live3d_hardware_acceptance_checklist_20260629.md)
- [Live3D hardware acceptance probe](docs/live3d_hardware_acceptance_probe_20260629.md)
- [Live3D hardware readiness gates probe](docs/live3d_hardware_readiness_gates_20260629.md)
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

Legacy lab code under `desperate/` is ignored local reference material. Do not
commit it from the parent repository; migrate needed behavior into `apps/`,
`packages/`, or `tools/` with focused tests and documentation.

## Remote Status

The parent repository no longer tracks submodules. Local legacy code under
`desperate/` may still have historical upstream origins, but that code is
ignored and outside the active runtime path.
