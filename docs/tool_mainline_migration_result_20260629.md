# Tool Mainline Migration Result

Date: 2026-06-29

## Branches

- `agent/yolo-mainline-migration`: `94828d1 Migrate YOLO annotator into tools`
- `agent/calibration-mainline-migration`: `921b64c Migrate fixed ChArUco calibration GUI into tools`
- Main merges:
  - `ad00b77 Merge YOLO annotator migration`
  - `3f394ba Merge fixed calibration GUI migration`

## YOLO Scope

Migrated the smallest annotator slice into `tools/yolo`:

- `tools/yolo/web/yolo-annotator/`
- `tools/yolo/yolo/scripts/serve_annotator.py`
- `tennisbot-yolo annotate`

Existing `tennisbot-yolo package create` and `package verify` remain in place.
Training, evaluation, camera collection, RKNN export, sprites, realtime GUI,
tests, datasets, runs, and model artifacts were not migrated.

## Calibration Scope

Recreated `tools/calibration` as a minimal fixed-board OpenCV GUI tool:

- `camera-calib-lab capture charuco-auto-gui`
- `camera-calib-lab capture stereo-charuco-auto-gui`
- fixed DFOptix ChArUco 14x9, `DICT_5X5_100`, 15 mm square, 11.25 mm marker
  config

Target registries, alternate board plugins, passive/phase GUIs, tests,
historical docs, captures, runs, and calibration packages were not migrated.

The minimal calibration migration writes capture session manifests and images.
Full calibration solve/export is intentionally not wired yet because that would
pull in the broader CameraCalibLab experiment/package framework.

## Verification

```text
cd tools/yolo
uv run tennisbot-yolo --help
uv run tennisbot-yolo annotate --help
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo

cd tools/yolo/web/yolo-annotator
bun run check

cd tools/calibration
uv run camera-calib-lab --help
uv run camera-calib-lab capture charuco-auto-gui --help
uv run camera-calib-lab capture stereo-charuco-auto-gui --help
uv run python - <<'PY'
from pathlib import Path
from camera_calib_lab.capture_gui import create_charuco_board, load_config
config = load_config(Path('configs/dfoptix_charuco_15mm_capture.yaml'))
board = create_charuco_board(config.target)
print(config.target)
print(type(board).__name__)
PY
```

All listed commands passed on the main worktree.
