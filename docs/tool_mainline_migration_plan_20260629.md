# Tool Mainline Migration Plan

Date: 2026-06-29

## Goal

Move both project-specific toolchains into top-level `tools/` so YOLO and
calibration are handled consistently:

- `tools/yolo`: tennis-ball annotation, dataset handling, training/eval/export,
  and runtime model package creation.
- `tools/calibration`: DFOptix ChArUco/OpenCV camera calibration GUI, solve, and
  runtime calibration artifact export.

The runtime boundary remains unchanged: apps and packages consume only
`artifacts/models/...` and `artifacts/calibration/...`.

## Migration Principle

Migrate the smallest useful working slice first, then fix errors surfaced by
tests and CLI smoke runs. Do not migrate generated data, local virtualenvs,
large model files, datasets, runs, or historical build outputs.

## YOLO Minimal Migration

Source: `desperate/TennisBallDetectorLab`.

Destination:

```text
tools/yolo/
  src/tennisbot_yolo/
  web/yolo-annotator/
  yolo/scripts/
  tests/
```

Move first:

- `web/yolo-annotator/`
- `src/tennis_ball_detector_lab/camera_collect.py`
- `src/tennis_ball_detector_lab/dataset.py`
- `src/tennis_ball_detector_lab/deliverable.py`
- `src/tennis_ball_detector_lab/evaluate.py`
- `src/tennis_ball_detector_lab/paths.py`
- Selected CLI behavior from `src/tennis_ball_detector_lab/cli.py`
- `yolo/scripts/serve_annotator.py`
- `yolo/scripts/build_current_backup_dataset.py`
- `yolo/scripts/train_yolo26n_cam1_700.py`
- `yolo/scripts/export_yolov8n_rknn_ptq.py`
- `yolo/scripts/extract_tennis_ball_sprites.py`
- Focused tests for dataset validation, camera collect, package/export, training
  dry-run, and annotator backend.

Keep or merge with existing `tools/yolo`:

- Keep the current runtime package contract and verifier in
  `tools/yolo/src/tennisbot_yolo/package.py`.
- Add migrated commands to the existing `tennisbot-yolo` CLI:
  `annotate`, `collect-camera`, `validate-dataset`, `build-dataset`, `train`,
  `eval`, `export-rknn`, `extract-sprites`, `package create`, and
  `package verify`.

Do not move in the first pass:

- `realtime_stereo_gui.py`
- HSV/realtime diagnostic GUI behavior
- local datasets, labels, training runs, model artifacts, `detector_package/`,
  `model_packages/`, CUDA shell setup helpers, or generated zips.

First acceptance checks:

```bash
cd tools/yolo
uv run pytest -q
cd web/yolo-annotator
bun run check
```

## Calibration Minimal Migration

Source: `desperate/CameraCalibLab`.

Destination:

```text
tools/calibration/
  src/camera_calib_lab/
  configs/
  tests/
```

Recreate `tools/calibration` as the mainline OpenCV calibration tool. Keep the
existing command name from the source project first:

```bash
uv run camera-calib-lab ...
```

Move first:

- `pyproject.toml` dependency shape for `camera-calib-lab`.
- `src/camera_calib_lab/cli.py`
- `src/camera_calib_lab/app/`
- `src/camera_calib_lab/capture/`
- `src/camera_calib_lab/commands/capture.py`
- `src/camera_calib_lab/commands/target.py`
- `src/camera_calib_lab/commands/detect.py`
- `src/camera_calib_lab/commands/calibrate.py`
- `src/camera_calib_lab/commands/package.py`
- `src/camera_calib_lab/commands/inspect.py`
- `src/camera_calib_lab/pipelines/capture_pipeline.py`
- `src/camera_calib_lab/pipelines/detection_pipeline.py`
- `src/camera_calib_lab/pipelines/calibration_pipeline.py`
- `src/camera_calib_lab/pipelines/package_pipeline.py`
- `src/camera_calib_lab/pipelines/target_pipeline.py`
- `src/camera_calib_lab/targets/`
- `src/camera_calib_lab/detection/`
- `src/camera_calib_lab/solvers/`
- `src/camera_calib_lab/packaging/`
- Required `contracts/`, `io/`, `reports/`, `registries/`, `utils/`, and
  `methods/` modules only as import errors require them.
- `configs/dfoptix_charuco_15mm_capture.yaml`
- Focused tests for CLI surfaces, target generation, capture command contracts,
  package export/verify, and GUI command construction.

Do not move in the first pass:

- simulation experiments
- method comparison matrix
- phase-screen experiments unless the OpenCV GUI import path requires a small
  shared helper
- legacy board frontend/static code
- generated captures, runs, calibration packages, local hardware evidence, or
  local `.venv`/cache files.

First acceptance checks:

```bash
cd tools/calibration
uv run pytest -q
uv run camera-calib-lab --help
uv run camera-calib-lab capture stereo-charuco-auto-gui --help
```

## Order

1. Migrate `tools/yolo` first because it already exists and has a small runtime
   package tool to extend.
2. Recreate `tools/calibration` from `CameraCalibLab` with only the OpenCV
   ChArUco calibration path.
3. Update README/current architecture after both tools have working CLI smoke
   checks.
4. Leave `desperate/` copies untouched until the mainline tools pass. Remove or
   archive them in a later deletion commit.

## Non-Goals For First Pass

- No ROS/Gazebo catch-loop changes.
- No Live3D behavior changes.
- No generated datasets, captures, model files, or calibration artifacts
  committed.
- No attempt to redesign package contracts during migration.
