# YOLO 0260701 Approx-5000 Batch12 Training - 2026-07-03

## Summary

This run regenerated sprites, synthesized an approximately 5000-image dataset, and trained YOLO with `batch=12`.

The data scope was intentionally limited to the large July 1 folder:

- Included: `tools/yolo/workspace/dataset/images/0260701`
- Included: `tools/yolo/workspace/dataset/labels/0260701`
- Excluded: older pre-July folders such as `cam1/device_a_indoor`

`batch=12` and `batch=16` are similar in speed on this setup because `imgsz=960` training is not purely GPU-bound. `batch=16` reduces step count, but each step is slower and has more memory pressure. Data loading, augmentation, validation, and fixed per-epoch overhead also remain similar, so epoch time does not scale linearly with batch size.

## Input Data

Source staging directory:

- `tools/yolo/workspace/runs/dataset_0260701_only_20260703`

The staging directory contains symlinks to the `0260701` image and label roots plus an empty exclusion file.

Counts before generation:

- Source images: 17,768
- Label files: 561
- Positive label files: 193
- Empty negative label files: 368
- Images without label files: 17,207
- Excluded images: 0

Generation was configured with `require_label_file_backgrounds = true`, so only images with a label file were eligible as augmentation backgrounds.

## Sprite Extraction

Command:

```bash
bun scripts/yolo.ts sprites extract \
  --images-root tools/yolo/workspace/runs/dataset_0260701_only_20260703/images \
  --labels-root tools/yolo/workspace/runs/dataset_0260701_only_20260703/labels \
  --excluded-file tools/yolo/workspace/runs/dataset_0260701_only_20260703/excluded_images.txt \
  --output-root tools/yolo/workspace/runs/sprites_0260701_20260703 \
  --overwrite
```

Result:

- Candidate sprites: 193
- Approved sprites used for this run: 193
- Skipped images: 17,575
- Sprite root: `tools/yolo/workspace/runs/sprites_0260701_20260703`

## Augmentation

Config:

- `tools/yolo/workspace/runs/augmentation_0260701_approx5000_20260703.toml`

Output dataset:

- `tools/yolo/workspace/runs/copy_paste_aug_0260701_approx5000_20260703`

Command:

```bash
bun scripts/yolo.ts augment copy-paste \
  --config tools/yolo/workspace/runs/augmentation_0260701_approx5000_20260703.toml
```

Resolved settings:

- Generated copy-paste positives: 4,500
- Generated augmented negatives: 500
- Original labeled images included in split: 561
- Total generated images: 5,000
- Total generated labels: 5,000
- Train images: 5,005
- Validation images: 556
- Split total: 5,561
- Split non-empty labels: 4,691
- Split empty labels: 870
- Split missing labels: 0
- Manifest kinds: `copy_paste=4500`, `negative_augmentation=500`

The generated dataset includes the original labeled `0260701` images in train/val in addition to the synthesized samples.

## Training

Command:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

project = Path('tools/yolo/workspace/runs/training').resolve()
model = YOLO('artifacts/models/tennis_ball_yolo/model.pt')
model.train(
    data='tools/yolo/workspace/runs/copy_paste_aug_0260701_approx5000_20260703/data.yaml',
    epochs=30,
    imgsz=960,
    batch=12,
    device='0',
    workers=8,
    patience=8,
    project=str(project),
    name='aug0260701_approx5000_batch12_20260703',
    seed=43,
    exist_ok=True,
)
PY
```

Training output:

- `tools/yolo/workspace/runs/training/aug0260701_approx5000_batch12_20260703`
- `weights/best.pt`
- `weights/last.pt`

Runtime and hardware:

- Epochs completed: 30
- Runtime: 0.653 hours
- GPU: NVIDIA GeForce RTX 4060 Ti, 7797 MiB
- Observed training memory: about 4.24-4.32 GiB
- Observed training speed: about 5.3 it/s

## Metrics

Final epoch from `results.csv`:

- Epoch: 30
- Precision: 0.91955
- Recall: 0.76875
- mAP50: 0.84898
- mAP50-95: 0.57284

Best epoch by mAP50-95 in `results.csv`:

- Epoch: 28
- Precision: 0.92130
- Recall: 0.75606
- mAP50: 0.84513
- mAP50-95: 0.57599

Final validation after reloading `best.pt`:

- Images: 556
- Instances: 480
- Precision: 0.919
- Recall: 0.757
- mAP50: 0.845
- mAP50-95: 0.576

## Verification

- Generated image count: 5,000
- Generated label count: 5,000
- Train/val split image count: 5,561
- Train/val missing label count: 0
- Training completed successfully and saved both `best.pt` and `last.pt`.
