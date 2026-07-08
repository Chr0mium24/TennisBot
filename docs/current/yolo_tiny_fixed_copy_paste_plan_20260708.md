# YOLO Tiny Fixed Copy-Paste Plan - 2026-07-08

## Reason

The previous final train-pool ROI+full run did not meet the objective. The
strongest failure was fixed-exposure small targets:

- Full-frame `imgsz=1536`, final raw benchmark: small recall `0.000`.
- Oracle `1024x576` ROI, `imgsz=960`: small recall only `0.500`.
- Benchmark fixed small median max box dimension: `6.64 px`.
- Train-pool fixed small median max box dimension: `10.33 px`.
- Benchmark fixed small with max dimension `<= 7 px`: `78.6%`.
- Train-pool fixed small with max dimension `<= 7 px`: `15.4%`.

This is a data distribution mismatch. Repeating the same training recipe for
more epochs is unlikely to fix it.

## Change

`augment build-final-trainset` now has an optional tiny copy-paste branch:

- `--tiny-positive-count`
- `--tiny-min-dim`
- `--tiny-max-dim`

The branch:

- uses only `train_pool` records from the frozen final raw manifest;
- prefers fixed-exposure positive source sprites;
- prefers fixed-exposure negative backgrounds;
- matches sprite source split to background split to avoid train/val leakage;
- pastes a real ball crop into a `1024x576` ROI background;
- scales the visible alpha bbox to the requested final label size;
- uses photometric/noise augmentation but no rotation for tiny samples, so the
  final bbox remains in the intended pixel range.

## Local Smoke

Command:

```bash
uv run --project tools/yolo --extra augment python -m tennisbot_yolo.cli augment build-final-trainset \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest.jsonl \
  --output-root tools/yolo/workspace/runs/final_trainpool_tiny_smoke_20260708 \
  --no-full-frame \
  --roi-positive-count 4 \
  --negative-crop-count 2 \
  --tiny-positive-count 30 \
  --tiny-min-dim 4 \
  --tiny-max-dim 8 \
  --seed 20260708
```

Result:

- generated images: `36`
- kind counts: `tiny_positive=30`, `roi_positive=4`, `roi_negative=2`
- split counts: `train=33`, `val=3`
- source split violations: `0`
- bad labels: `0`
- tiny final label max dimension: min `4.0`, p25 `5.0`, median `6.0`, p75 `7.0`, max `8.0`

## Next Experiment

Build a full train set on the remote GPU machine:

```bash
uv run --project tools/yolo --extra augment python -m tennisbot_yolo.cli augment build-final-trainset \
  --manifest tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl \
  --output-root tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708 \
  --roi-positive-count 5000 \
  --negative-crop-count 1500 \
  --tiny-positive-count 6000 \
  --tiny-min-dim 4 \
  --tiny-max-dim 8 \
  --seed 20260708
```

Train from the previous best model first, because it already improved
large/medium and precision:

```python
from ultralytics import YOLO

model = YOLO("tools/yolo/workspace/runs/training/final_trainpool_roi_full_imgsz960_batch32_20260708/weights/best.pt")
model.train(
    data="tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml",
    imgsz=960,
    epochs=35,
    patience=8,
    batch=32,
    device=0,
    workers=0,
    project="/home/anilam/Codes/TennisBot/tools/yolo/workspace/runs/training",
    name="final_trainpool_tiny_fixed_cp_imgsz960_batch32_20260708",
    pretrained=True,
    save=True,
    save_period=10,
    cache=False,
    deterministic=True,
    seed=0,
    mosaic=0.0,
    mixup=0.0,
    copy_paste=0.0,
    cutmix=0.0,
    auto_augment=None,
    erasing=0.0,
    hsv_h=0.0,
    hsv_s=0.0,
    hsv_v=0.0,
    degrees=0.0,
    translate=0.0,
    scale=0.0,
    shear=0.0,
    perspective=0.0,
    flipud=0.0,
    fliplr=0.0,
)
```

Evaluate on the frozen final raw benchmark at `imgsz=960`, `1280`, and `1536`.
The success target remains final raw recall near or above `0.90` with estimated
stereo FPS above `50`, reported by auto/fixed and small/medium/large buckets.

