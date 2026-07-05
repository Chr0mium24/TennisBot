# Search-S3k Pseudo + Small Hard-Negative + Targeted Synthetic Plan - 2026-07-05

## Goal

Continue toward held-out recall above `0.90` by combining the strongest pieces
from prior experiments:

- S3d pseudo-positive base for recall;
- S3j small hard-negative subset for suppressing background peaks;
- S3h targeted synthetic distribution for the held-out miss pattern.

S3j reached `0.753` recall with better precision than S3d, but still did not
beat S3d's `0.774`. S3k keeps the S3j label root and replaces random synthetic
with targeted synthetic positives.

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3k_temporal_heatmap_w5_960x540_pseudo_hardneg300_targeted_synth1000_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705/labels \
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
  --synthetic-count 1000 \
  --synthetic-motion-px-min 4 \
  --synthetic-motion-px-max 28 \
  --synthetic-motion-angle-deg-min 210 \
  --synthetic-motion-angle-deg-max 330 \
  --synthetic-center-x-min 0.42 \
  --synthetic-center-x-max 0.58 \
  --synthetic-center-y-min 0.45 \
  --synthetic-center-y-max 0.68 \
  --synthetic-blur-probability 0.35 \
  --output-markdown docs/current/yolo_search_s3k_pseudo_hardneg_targeted_result_20260705.md
```

## Decision Rule

- If S3k exceeds S3d recall `0.774`, continue tuning targeted synthetic count.
- If S3k stays below S3d, the current generated-data path is exhausted and the
  next work must be reviewed real positives around the held-out miss pattern.
- Completion still requires verified recall above `0.90`.
