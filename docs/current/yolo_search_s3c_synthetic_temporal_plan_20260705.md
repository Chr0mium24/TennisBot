# Search-S3c Synthetic Temporal Heatmap Plan - 2026-07-05

## Goal

Move toward the requested target: validation recall above 90%.

Current best model is Search-S3b:

- best recall: `0.559`;
- best precision: `0.929`;
- best F1: `0.698`;
- observed high-recall epoch: about `0.624` recall with lower precision.

This is still far from `0.90` recall. The main bottleneck is data volume:
Search-S3b trained on only 96 real positive 5-frame windows.

## Change

Add online synthetic temporal positives for heatmap training:

- choose non-validation, non-positive background frames;
- choose approved real ball sprites;
- paste one sprite through a 5-frame linear motion path;
- generate a Gaussian heatmap at the center-frame ball position;
- keep validation strictly on real held-out `20260701_155008` frames.

This increases positive training samples without polluting validation.

## Training Trial

Train Search-S3c from scratch with real + synthetic positives:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3c_temporal_heatmap_w5_960x540_synth2000_20260705 \
  --device cuda:0 \
  --epochs 55 \
  --patience 14 \
  --batch 4 \
  --workers 4 \
  --input-width 960 \
  --input-height 540 \
  --window 5 \
  --sigma 4.0 \
  --radius-px 12 \
  --max-negative-ratio 1.5 \
  --synthetic-count 2000 \
  --synthetic-motion-px-max 20 \
  --output-markdown docs/current/yolo_search_s3c_synthetic_temporal_result_20260705.md
```

## Decision Rule

- If held-out recall reaches `>0.90`, audit precision and candidate quality
  before marking the goal complete.
- If recall improves but stays below `0.90`, use S3c to mine pseudo-labels and
  add more reviewed continuous cam1/cam2 labels.
- If recall regresses, reduce synthetic ratio or make synthetic generation more
  realistic before more training.
