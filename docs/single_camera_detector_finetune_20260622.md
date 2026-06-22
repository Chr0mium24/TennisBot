# Single-Camera Detector Fine-Tune Flow - 2026-06-22

## Goal

Fine-tune the tennis-ball YOLO model from one live camera only. Since the two
cameras are expected to have the same optics and ball appearance, one labeled
camera stream is enough for a quick detector adaptation pass.

## Flow

1. Capture still training images directly from one camera into the YOLO dataset.
2. Annotate those images in the existing local annotator.
3. Continue training from `yolo/models/yolo/best.pt`.
4. Point realtime stereo GUI at the new `weights/best.pt`.

This avoids the explicit `record mp4 -> extract frames` step. YOLO training
still uses image/label pairs, so the capture command saves sampled still frames
while the camera is running.

## Commands

Capture one camera:

```bash
cd /home/cr/Codes/TennisBot/TennisBallDetectorLab
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl collect-camera \
  --device /dev/video0 \
  --camera cam1 \
  --width 1920 \
  --height 1080 \
  --fps 30 \
  --duration 30 \
  --sample-every 5 \
  --dataset-tag device_a_indoor \
  --session indoor_ball_sample
```

Annotate:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl annotate
```

Open `http://127.0.0.1:8765`, draw a box around the ball, and press `D` for
frames where there is no ball.

Fine-tune from the current model:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl train \
  --camera cam1 \
  --limit 300 \
  --allow-fewer \
  --model yolo/models/yolo/best.pt \
  --epochs 50 \
  --imgsz 1280 \
  --device 0 \
  --name finetune_indoor_cam1
```

Run realtime stereo with the fine-tuned model:

```bash
YOLO_CONFIG_DIR=/tmp/Ultralytics env UV_CACHE_DIR=/tmp/uv-cache uv run tbl stereo-gui \
  --detector yolo \
  --model yolo/runs/training/finetune_indoor_cam1/weights/best.pt
```

## Implementation

- Added `tbl collect-camera`.
- The command saves sampled camera frames directly to `yolo/dataset/images/<camera>/<dataset-tag>`.
- Matching labels mirror that structure under `yolo/dataset/labels/<camera>/<dataset-tag>`.
- Labels are not pre-created by default so the annotator treats new frames as
  unlabeled. `--write-empty-labels` is available only when pre-marking negatives
  is desired.
- `--dataset-tag` separates devices, lighting setups, or collection sessions.
  It defaults to `--session` if omitted.
- A per-session manifest is written under `yolo/dataset/capture_manifests/`.
- Dataset validation, `tbl train`, and `tbl build-dataset` support recursive
  `labels/<camera>/<dataset-tag>/...` folders.

## Verification

Commands:

```bash
env UV_CACHE_DIR=/tmp/uv-cache uv run python -m compileall -q src tests
env UV_CACHE_DIR=/tmp/uv-cache PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
env UV_CACHE_DIR=/tmp/uv-cache uv run tbl collect-camera --help
```

Results:

- `compileall`: passed.
- `pytest`: `29 passed`.
- `tbl collect-camera --help`: passed and lists single-camera capture options.
