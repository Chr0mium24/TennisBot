# Evaluation Report

YOLO package promoted from the `0260701`-only batch12 training run on 2026-07-03.

- Source dataset: `tools/yolo/workspace/runs/copy_paste_aug_0260701_approx5000_20260703`
- Generated images: 5000
- Generated copy-paste positives: 4500
- Generated augmented negatives: 500
- Original labeled images included in split: 561
- Train images: 5005
- Validation images: 556
- Validation instances: 480
- Training: 30 epochs, `imgsz=960`, `batch=12`
- Best weights: `tools/yolo/workspace/runs/training/aug0260701_approx5000_batch12_20260703/weights/best.pt`

Final validation after reloading `best.pt`:

- Precision: 0.919
- Recall: 0.757
- mAP50: 0.845
- mAP50-95: 0.576

Full experiment notes are in `docs/current/yolo_0260701_approx5000_batch12_training_20260703.md`.
