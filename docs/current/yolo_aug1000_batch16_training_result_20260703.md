# YOLO Augmentation 1000 Batch16 Training Result - 2026-07-03

## Dataset

Generated trial dataset:

- Root: `tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703`
- Generated images: 1000
- Generated copy-paste positives: 900
- Generated augmented negatives: 100
- Original labeled images included in split: 628
- Train images: 1465
- Validation images: 163
- Non-empty labels in split: 1154
- Empty negative labels in split: 474

Augmentation background rule:

- Only images with a corresponding label file are allowed as backgrounds.
- Missing-label images are not treated as negative backgrounds.

## Training

Training run:

- Run directory: `tools/yolo/workspace/runs/training/aug1000_batch16_20260703`
- Base model: `artifacts/models/tennis_ball_yolo/model.pt`
- Epochs: 30
- Image size: 960
- Batch size: 16
- Device: CUDA `0`
- GPU: NVIDIA GeForce RTX 4060 Ti
- Peak observed training memory: about 5.7 GB

Command:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

project = Path("tools/yolo/workspace/runs/training").resolve()
model = YOLO("artifacts/models/tennis_ball_yolo/model.pt")
model.train(
    data="tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/data.yaml",
    epochs=30,
    imgsz=960,
    batch=16,
    device="0",
    workers=8,
    patience=8,
    project=str(project),
    name="aug1000_batch16_20260703",
    seed=42,
    exist_ok=True,
)
PY
```

## Metrics

Best validation metrics from `results.csv`:

- Best mAP50: 0.80307 at epoch 28
- Best mAP50-95: 0.62706 at epoch 30

Final epoch 30:

- Precision: 0.89162
- Recall: 0.68644
- mAP50: 0.79338
- mAP50-95: 0.62706

Weights:

- Best: `tools/yolo/workspace/runs/training/aug1000_batch16_20260703/weights/best.pt`
- Last: `tools/yolo/workspace/runs/training/aug1000_batch16_20260703/weights/last.pt`

## Verification

Targeted YOLO tool tests passed:

```bash
uv run --project tools/yolo pytest tools/yolo/tests
```

Full repository test collection was not used for this result because it collects
archived `desperate/` experiments that require packages not installed in the
`tools/yolo` uv environment.
