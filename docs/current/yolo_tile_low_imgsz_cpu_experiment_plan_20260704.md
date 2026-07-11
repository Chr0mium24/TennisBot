# YOLO Tile Low-Imgsz CPU Experiment Plan - 2026-07-04

## Question

Validate whether tiled 4K inference with a low `imgsz` model can be more
efficient than full-frame inference for the final CPU edge deployment.

The specific question is not whether tile can improve recall at any cost. The
question is whether `tile + low imgsz` can beat `full_4k + higher imgsz` on the
accuracy/FPS tradeoff.

## First-Principles Readout

For the current exhaustive tile implementation, model compute is roughly:

```text
model_mpix_per_stereo = sources_per_stereo * imgsz * imgsz / 1_000_000
```

For one stereo frame:

- `full_4k` uses `2` sources: left full frame and right full frame.
- `tile_2048x1216` uses `8` sources: `4` tiles per camera.
- `tile_1536x864` uses `18` sources: `9` tiles per camera.

This means exhaustive tile only becomes cheaper than full-frame high `imgsz`
when `imgsz` is reduced aggressively. At equal compute, the geometric ball scale
is not better:

| Pair | model MPix/stereo | effective scale vs source width | Readout |
|---|---:|---:|---|
| `full_4k imgsz=640` | 0.82 | 640 / 3840 = 0.167 | fastest full baseline |
| `tile_2048x1216 imgsz=320` | 0.82 | 320 / 2048 = 0.156 | same compute, slightly smaller ball |
| `full_4k imgsz=960` | 1.84 | 960 / 3840 = 0.250 | current practical full candidate |
| `tile_1536x864 imgsz=320` | 1.84 | 320 / 1536 = 0.208 | same compute, smaller ball |
| `tile_2048x1216 imgsz=512` | 2.10 | 512 / 2048 = 0.250 | same ball scale as full 960, more compute |
| `full_4k imgsz=1280` | 3.28 | 1280 / 3840 = 0.333 | higher-recall full candidate |
| `tile_2048x1216 imgsz=640` | 3.28 | 640 / 2048 = 0.312 | same compute, slightly smaller ball |
| `full_4k imgsz=1536` | 4.72 | 1536 / 3840 = 0.400 | expensive full candidate |
| `tile_1536x864 imgsz=512` | 4.72 | 512 / 1536 = 0.333 | same compute, smaller ball |

Initial hypothesis:

- Exhaustive `tile + low imgsz` is unlikely to be both faster and more accurate
  than `full_4k + higher imgsz`.
- Exhaustive tile may still be useful if it beats a low full-frame baseline on
  recall and the CPU FPS remains acceptable.
- Tile becomes genuinely attractive for CPU only if it is sparse/ROI-gated, for
  example one or two tiles per camera based on a cheap coarse pass or previous
  real detections. That is a separate runtime strategy; it is not the current
  exhaustive tile path.

## Existing Baseline

Existing 1000-image training result that can be reused:

- Dataset: `tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703`
- Training run: `tools/yolo/workspace/runs/training/aug1000_batch16_20260703`
- Epochs: `30`
- Batch: `16`
- Train `imgsz`: `960`
- Final metrics: precision `0.89162`, recall `0.68644`, mAP50 `0.79338`,
  mAP50-95 `0.62706`

## Training Matrix

Use the same 1000 generated images and validation split for all runs.

| Run | Base model | Dataset | Train imgsz | Epochs | Batch | Purpose |
|---|---|---|---:|---:|---:|---|
| `aug1000_batch16_imgsz512_20260704` | current package `model.pt` | `copy_paste_aug_1000_trial_20260703` | 512 | 30 | 16 | low-imgsz CPU candidate |
| `aug1000_batch16_imgsz640_20260704` | current package `model.pt` | `copy_paste_aug_1000_trial_20260703` | 640 | 30 | 16 | main low-imgsz CPU candidate |
| `aug1000_batch16_20260703` | existing result | `copy_paste_aug_1000_trial_20260703` | 960 | 30 | 16 | existing baseline |
| `aug1000_batch16_imgsz1280_20260704` | current package `model.pt` | `copy_paste_aug_1000_trial_20260703` | 1280 | 30 | 16 target, reduce only on OOM | high-recall full-frame reference |

Training command template:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

imgsz = 640
name = f"aug1000_batch16_imgsz{imgsz}_20260704"
project = Path("tools/yolo/workspace/runs/training").resolve()
model = YOLO("artifacts/models/tennis_ball_yolo/model.pt")
model.train(
    data="tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/data.yaml",
    epochs=30,
    imgsz=imgsz,
    batch=16,
    device="0",
    workers=8,
    patience=8,
    project=str(project),
    name=name,
    seed=44 + imgsz,
    exist_ok=True,
)
PY
```

## Inference Matrix

Evaluate each trained model on the same validation list.

| Method | Profiles | Inference imgsz values | Why |
|---|---|---|---|
| Full frame | `full_4k` | 512, 640, 960, 1280 | CPU baseline and high-recall reference |
| Exhaustive 2x2 tile | `tile_2048x1216 overlap=160` | 320, 416, 512, 640 | tests low-imgsz tile efficiency |
| Exhaustive 3x3 tile | `tile_1536x864 overlap=160` | 320, 416, 512 | tests stronger local scale at higher source count |

Primary comparisons:

- `tile_2048x1216 imgsz=320` vs `full_4k imgsz=640`
- `tile_2048x1216 imgsz=512` vs `full_4k imgsz=960`
- `tile_2048x1216 imgsz=640` vs `full_4k imgsz=1280`
- `tile_1536x864 imgsz=320` vs `full_4k imgsz=960`
- `tile_1536x864 imgsz=512` vs `full_4k imgsz=1536`

## Metrics

Accuracy metrics on real validation images:

- recall at IoU `0.5`
- precision at IoU `0.5`
- F1 at IoU `0.5`
- false positives per image
- missed positive images

Speed metrics on CPU:

- median ms per single image
- estimated stereo FPS as `1000 / (2 * median_single_image_ms)` for full frame
- estimated stereo FPS with actual source count for tile
- p95 ms

Decision metric:

```text
score = recall@0.5 / median_stereo_ms
```

Use score only as a ranking aid. The final choice must satisfy minimum recall
and false-positive limits first.

## Expected Decision

If exhaustive tile does not beat full-frame on recall at similar or lower CPU
time, keep the runtime default on full-frame low/mid `imgsz`.

If exhaustive tile only improves recall while being slower, use it as a
debug/validation mode, not the default CPU edge path.

If tile is needed for recall, the next CPU-oriented experiment should be sparse
tile:

- low `imgsz` full-frame pass to locate a candidate;
- one local tile per camera around the candidate or previous real detection;
- high-confidence fallback to full-frame if the ROI is lost.

Sparse tile is the only tile strategy that can plausibly improve both accuracy
and FPS on CPU, because it reduces tile sources from `4` or `9` per camera to
about `1` per camera.

## Dry-Run Compute Matrix

Generated with:

```bash
uv run scripts/yolo.py benchmark tiles --dry-run \
  --imgsz-values 320,416,512,640,960,1280,1536 \
  --tile-profile full_4k:3840:2160:0 \
  --tile-profile tile_2048x1216:2048:1216:160 \
  --tile-profile tile_1536x864:1536:864:160
```

| profile | tile | overlap | imgsz | tiles/cam | sources/stereo | model MPix | crop MPix |
|---|---:|---:|---:|---:|---:|---:|---:|
| full_4k | 3840x2160 | 0 | 320 | 1 (1x1) | 2 | 0.20 | 16.59 |
| full_4k | 3840x2160 | 0 | 416 | 1 (1x1) | 2 | 0.35 | 16.59 |
| full_4k | 3840x2160 | 0 | 512 | 1 (1x1) | 2 | 0.52 | 16.59 |
| full_4k | 3840x2160 | 0 | 640 | 1 (1x1) | 2 | 0.82 | 16.59 |
| full_4k | 3840x2160 | 0 | 960 | 1 (1x1) | 2 | 1.84 | 16.59 |
| full_4k | 3840x2160 | 0 | 1280 | 1 (1x1) | 2 | 3.28 | 16.59 |
| full_4k | 3840x2160 | 0 | 1536 | 1 (1x1) | 2 | 4.72 | 16.59 |
| tile_2048x1216 | 2048x1216 | 160 | 320 | 4 (2x2) | 8 | 0.82 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 416 | 4 (2x2) | 8 | 1.38 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 512 | 4 (2x2) | 8 | 2.10 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 640 | 4 (2x2) | 8 | 3.28 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 960 | 4 (2x2) | 8 | 7.37 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 1280 | 4 (2x2) | 8 | 13.11 | 19.92 |
| tile_2048x1216 | 2048x1216 | 160 | 1536 | 4 (2x2) | 8 | 18.87 | 19.92 |
| tile_1536x864 | 1536x864 | 160 | 320 | 9 (3x3) | 18 | 1.84 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 416 | 9 (3x3) | 18 | 3.12 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 512 | 9 (3x3) | 18 | 4.72 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 640 | 9 (3x3) | 18 | 7.37 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 960 | 9 (3x3) | 18 | 16.59 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 1280 | 9 (3x3) | 18 | 29.49 | 23.89 |
| tile_1536x864 | 1536x864 | 160 | 1536 | 9 (3x3) | 18 | 42.47 | 23.89 |
