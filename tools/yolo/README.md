# TennisBot YOLO Tool Boundary

Date: 2026-06-28

`tools/yolo` is the future home for TennisBot tennis-ball detector tooling:
annotation, dataset validation, training, evaluation, model export, and model
package publication. In Wave 1 this directory is documentation only. The
working implementation remains in `TennisBallDetectorLab`.

The live runtime must consume exported model packages from `artifacts/models/`.
It must not import training, annotation, dataset, or export internals from this
tool.

## Current To Target Command Map

Run current commands from `TennisBallDetectorLab/`. Target commands are the
intended post-migration shape from the TennisBot repository root.

| Workflow | Current command | Target command |
| --- | --- | --- |
| Install Python deps | `uv sync` | `uv sync --package tennisbot-yolo` |
| Run Python tests | `uv run pytest` | `uv run pytest tools/yolo/tests` |
| Install annotator deps | `bun install` | `cd tools/yolo/web/yolo-annotator && bun install` |
| Typecheck annotator | `bun run check` | `cd tools/yolo/web/yolo-annotator && bun run check` |
| Serve annotator | `uv run tbl annotate` | `uv run tennisbot-yolo annotate` |
| Open annotator | `http://127.0.0.1:8765` | `http://127.0.0.1:8765` |
| Capture camera frames | `uv run tbl collect-camera --device /dev/video0 --camera cam1 ...` | `uv run tennisbot-yolo collect-camera --device /dev/video0 --camera cam1 ...` |
| Validate dataset | `uv run tbl validate-dataset` | `uv run tennisbot-yolo validate-dataset` |
| Validate labels without images | `uv run tbl validate-dataset --allow-missing-images` | `uv run tennisbot-yolo validate-dataset --allow-missing-images` |
| Build train/val manifests | `uv run tbl build-dataset` | `uv run tennisbot-yolo build-dataset` |
| Build per-camera manifests | `uv run tbl build-dataset --camera cam1` | `uv run tennisbot-yolo build-dataset --camera cam1` |
| Dry-run training | `uv run tbl train --data-yaml yolo/dataset_configs/current_plus_low_bitrate_backup/data.yaml --dry-run` | `uv run tennisbot-yolo train --data-yaml tools/yolo/dataset_configs/current_plus_low_bitrate_backup/data.yaml --dry-run` |
| Train model | `uv run tbl train --data-yaml yolo/dataset_configs/current_plus_low_bitrate_backup/data.yaml --model yolov8n.pt --device 0 --name tennis_ball_yolov8n` | `uv run tennisbot-yolo train --data-yaml tools/yolo/dataset_configs/current_plus_low_bitrate_backup/data.yaml --model yolov8n.pt --device 0 --name tennis_ball_yolov8n` |
| Write eval report | `uv run tbl eval --allow-missing-images` | `uv run tennisbot-yolo eval --allow-missing-images` |
| Export ONNX only | `uv run tbl export-rknn --model yolo/runs/training/tennis_ball_yolov8n/weights/best.pt --skip-rknn` | `uv run tennisbot-yolo export-rknn --model artifacts/models/training/tennis_ball_yolov8n/weights/best.pt --skip-rknn` |
| Export RKNN | `uv run --with rknn-toolkit2 --with torchvision==0.19.0 --with onnx==1.17.0 tbl export-rknn --model yolo/runs/training/tennis_ball_yolov8n/weights/best.pt --target-platform rk3576 --calibration-count 200` | `uv run --with rknn-toolkit2 --with torchvision==0.19.0 --with onnx==1.17.0 tennisbot-yolo export-rknn --model artifacts/models/training/tennis_ball_yolov8n/weights/best.pt --target-platform rk3576 --calibration-count 200` |
| Publish runtime model package | `uv run tbl package --model-pt ... --model-onnx ... --model-rknn ... --eval-report runs/eval/eval_report.md --eval-metrics runs/eval/eval_metrics.json` | `uv run tennisbot-yolo package --output-dir artifacts/models/tennis_ball_yolo --model-pt ... --model-onnx ... --model-rknn ... --eval-report artifacts/models/eval/eval_report.md --eval-metrics artifacts/models/eval/eval_metrics.json` |
| Extract sprites for UI/debug assets | `uv run tbl extract-sprites ...` | `uv run tennisbot-yolo extract-sprites ...` |
| Legacy direct frame extraction | `uv run python yolo/scripts/extract_frames.py` | `uv run tennisbot-yolo extract-frames ...` |
| Legacy direct image resize | `uv run python yolo/scripts/resize_images.py` | `uv run tennisbot-yolo resize-images ...` |
| Legacy CUDA zip bundle | `uv run python yolo/scripts/make_yolo_zip.py` | `uv run tennisbot-yolo export-training-bundle ...` |

The target CLI name is provisional. The important boundary is that future
commands are invoked as a TennisBot YOLO tool and publish only runtime packages
to apps.

## Target Layout

```text
tools/yolo/
  README.md
  MODEL_PACKAGE_CONTRACT.md
  MIGRATION_CHECKLIST.md
  src/                         # future Python package
  tests/                       # future tool tests
  web/yolo-annotator/          # future TypeScript annotator
  dataset_configs/             # lightweight generated/curated configs only
  configs/                     # model and experiment configs
  scripts/                     # temporary migration shims only
```

Large or generated content must stay out of this tracked tool directory unless
the lead explicitly approves a small, reviewable fixture:

- datasets and labels in active user work;
- training runs;
- exported `.pt`, `.onnx`, `.rknn`, and similar model artifacts;
- local package outputs.

Canonical runtime model packages belong under:

```text
artifacts/models/tennis_ball_yolo/
```

## Runtime Boundary

`apps/live3d` consumes the model package contract in
[`MODEL_PACKAGE_CONTRACT.md`](MODEL_PACKAGE_CONTRACT.md). It should load:

- package metadata;
- label names;
- preprocessing settings;
- postprocessing settings;
- exactly one compatible runtime model artifact.

`apps/live3d` should not consume:

- YOLO dataset folders;
- annotator source;
- training scripts;
- Ultralytics run directories;
- RKNN calibration workspaces.

## Migration Checklist

Use [`MIGRATION_CHECKLIST.md`](MIGRATION_CHECKLIST.md) for the later
`TennisBallDetectorLab` move. The checklist is intentionally separate from this
Wave 1 boundary branch because the current lab has user-owned dirty dataset
changes.
