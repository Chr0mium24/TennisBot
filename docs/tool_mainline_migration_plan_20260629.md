# Tool Mainline Migration Plan

Date: 2026-06-29

## Goal

Move both project-specific toolchains into top-level `tools/` so YOLO and
calibration are handled consistently, using the smallest runnable slice first:

- `tools/yolo`: tennis-ball annotation frontend/backend plus existing runtime
  model package creation.
- `tools/calibration`: fixed DFOptix ChArUco/OpenCV mono and stereo capture GUI
  plus the backend needed by those two GUI commands.

The runtime boundary remains unchanged: apps and packages consume only
`artifacts/models/...` and `artifacts/calibration/...`.

## Migration Principle

Migrate the smallest useful working slice first, then fix errors surfaced by
CLI smoke runs. Do not migrate generated data, local virtualenvs, tests,
historical docs, large model files, datasets, runs, or historical build outputs.

## YOLO Minimal Migration

Source: `desperate/TennisBallDetectorLab`.

Destination:

```text
tools/yolo/
  src/tennisbot_yolo/
  web/yolo-annotator/
  yolo/scripts/
```

Move first:

- `web/yolo-annotator/`
- `src/tennis_ball_detector_lab/dataset.py`
- `src/tennis_ball_detector_lab/paths.py`
- `yolo/scripts/serve_annotator.py`
- Minimal selected CLI behavior from `src/tennis_ball_detector_lab/cli.py`:
  `annotate` only.

Keep or merge with existing `tools/yolo`:

- Keep the current runtime package contract and verifier in
  `tools/yolo/src/tennisbot_yolo/package.py`.
- Add only `annotate` to the existing `tennisbot-yolo` CLI.
- Keep existing `package create` and `package verify`.

Do not move in the first pass:

- tests and historical docs
- camera collection
- training
- evaluation
- RKNN export
- sprite extraction
- dataset manifest builders
- `realtime_stereo_gui.py`
- HSV/realtime diagnostic GUI behavior
- local datasets, labels, training runs, model artifacts, `detector_package/`,
  `model_packages/`, CUDA shell setup helpers, or generated zips.

First acceptance checks:

```bash
cd tools/yolo
uv run tennisbot-yolo --help
uv run tennisbot-yolo annotate --help
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
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
```

Recreate `tools/calibration` as the mainline OpenCV calibration tool. Keep the
existing command name from the source project first:

```bash
uv run camera-calib-lab ...
```

Move first:

- `pyproject.toml` dependency shape for `camera-calib-lab`.
- `src/camera_calib_lab/cli.py`
- `src/camera_calib_lab/app/charuco_auto_capture_app.py`
- `src/camera_calib_lab/app/stereo_charuco_auto_capture_app.py`
- `src/camera_calib_lab/app/display_windows.py`
- `src/camera_calib_lab/app/keyboard.py`
- `src/camera_calib_lab/app/overlay.py`
- `src/camera_calib_lab/capture/`
- `src/camera_calib_lab/commands/capture.py`
- `src/camera_calib_lab/pipelines/capture_pipeline.py`
- `src/camera_calib_lab/pipelines/calibration_pipeline.py`
- a small fixed target module for the project board:
  DFOptix ChArUco 14x9, `DICT_5X5_100`, 15 mm squares, 11.25 mm markers.
- `src/camera_calib_lab/detection/charuco.py`
- `src/camera_calib_lab/detection/base.py`
- `src/camera_calib_lab/detection/quality.py`
- `src/camera_calib_lab/detection/subpixel.py`
- `src/camera_calib_lab/solvers/`
- Required `contracts/`, `io/`, `reports/`, `registries/`, `utils/`, and
  `methods/` modules only as import errors require them for these two commands.
  Prefer deleting registry/plugin lookups over migrating them when the only
  needed target is the fixed project board.
- `configs/dfoptix_charuco_15mm_capture.yaml`

Do not move in the first pass:

- tests and historical docs
- passive GUI and phase GUI
- standalone target CLI
- target registry, checkerboard, circle-grid, phase-screen, and other board
  plugins
- inspect/detect/package command groups
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
uv run camera-calib-lab --help
uv run camera-calib-lab capture charuco-auto-gui --help
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
