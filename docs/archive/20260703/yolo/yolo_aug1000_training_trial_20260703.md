# YOLO Augmentation 1000 Training Trial - 2026-07-03

## Goal

Run a smaller YOLO training trial before committing to the 5000-image augmented
dataset.

## Reason For Change

An initial 5000-image augmentation was generated successfully, but the first
training attempt used `imgsz=1280` with automatic batch selection. On the local
RTX 4060 Ti 8GB GPU, Ultralytics selected batch size 2 and showed batch size 4
would run out of memory at 1280. The trial was stopped and replaced with this
smaller run.

## Data Rules

- Only images with a corresponding label file may be used as augmentation
  backgrounds.
- Missing-label images are not treated as negative backgrounds.
- Generated trial set target: 1000 images.
- Positive copy-paste target: 900 generated images.
- Negative augmentation target: 100 generated images.
- Original labeled images are also included in the final split.
- Split ratio: 90% train, 10% validation.

Current original labeled input counts:

- Original images with label files: 628
- Original non-empty positive labels: 254
- Original empty negative labels: 374
- Missing-label images excluded from augmentation backgrounds: 17261
- Excluded images: 11

## Commands

Approve current sprites:

```bash
uv run --project tools/yolo --extra augment python - <<'PY'
import shutil
from pathlib import Path
from tennisbot_yolo.sprites import copy_reviewed_sprite, list_candidate_metadata

sprites_root = Path("tools/yolo/workspace/runs/sprites")
approved_root = sprites_root / "approved"
if approved_root.exists():
    shutil.rmtree(approved_root)
approved_root.mkdir(parents=True)

for metadata in list_candidate_metadata(sprites_root):
    metadata_path = sprites_root / "candidates" / metadata["files"]["metadata"]
    copy_reviewed_sprite(sprites_root, metadata, metadata_path, "approved")
PY
```

Generate augmentation:

```bash
bun scripts/yolo.ts augment copy-paste \
  --config tools/yolo/workspace/runs/augmentation_1000_trial_20260703.toml
```

Train:

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
    batch=4,
    device="0",
    workers=8,
    patience=8,
    project=str(project),
    name="aug1000_trial_20260703",
    seed=42,
    exist_ok=True,
)
PY
```

## Results

Pending.
