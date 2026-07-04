# Search-S3b Temporal Heatmap Plan - 2026-07-05

## Purpose

Train a second temporal search model before touching runtime distillation.
Search-S3 proved the direction is viable, but its validation recall was still
too low for a teacher.

This is an offline vision experiment only. It does not validate ROS/Gazebo,
stereo triangulation, target prediction, or chassis control.

## Why Another Model

Do not train another single-frame YOLO neck first. Search-S2 already showed
that single-frame YOLO full-frame search is not the right next step:

- validation recall stayed near `0.07692`;
- held-out replay recall stayed near `0.184-0.205`;
- full-frame CPU search dominated the runtime.

Search-S3 temporal heatmap did better:

- best validation recall `0.462`;
- best validation precision `0.741`;
- best F1 `0.570`;
- oracle recall `0.548`.

That means the next model should push the same temporal/heatmap direction, not
restart a YOLO architecture sweep.

## Model

| Field | Search-S3 | Search-S3b |
|---|---:|---:|
| Window | 3 frames | 5 frames |
| Input | 640x360 | 960x540 |
| Target | Gaussian heatmap | Gaussian heatmap |
| Role | teacher prototype | higher-recall teacher |
| Runtime target | no | no |

Search-S3b spends more pixels and temporal context to test the recall ceiling.
It is not expected to be CPU-real-time.

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3b_temporal_heatmap_w5_960x540_20260705 \
  --device cuda:0 \
  --epochs 45 \
  --patience 12 \
  --batch 4 \
  --workers 4 \
  --input-width 960 \
  --input-height 540 \
  --window 5 \
  --sigma 4.0 \
  --radius-px 12 \
  --max-negative-ratio 1.5 \
  --output-markdown docs/current/yolo_search_s3b_temporal_heatmap_result_20260705.md
```

## Decision Rule

- If recall improves materially over Search-S3, use S3b as the teacher path and
  next mine pseudo-labels.
- If recall does not improve, stop increasing model/input size and fix data:
  add more labeled continuous 4K cam1/cam2 positive sequences and hard
  negatives.
