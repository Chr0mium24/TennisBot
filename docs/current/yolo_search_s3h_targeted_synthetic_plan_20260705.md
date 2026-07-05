# Search-S3h Targeted Synthetic Temporal Plan - 2026-07-05

## Goal

Continue toward held-out recall above `0.90` by adding targeted synthetic
training signal for the current S3d miss pattern.

The S3d held-out audit showed that most remaining misses are high-score bad
localizations, not low-score misses. The model is distracted by ceiling/left
background structure while the labeled ball is around the net/center region.
Top-k heatmap selection did not improve recall.

## Change

Add configurable targeted synthetic generation:

- normalized center x range;
- normalized center y range;
- motion angle range in degrees;
- existing random synthetic behavior remains the default.

For S3h, synthesize balls near the held-out failure region while still excluding
the held-out `20260701_155008` sequence from training backgrounds and sprites.

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3h_temporal_heatmap_w5_960x540_targeted_synth2500_20260705 \
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
  --synthetic-count 2500 \
  --synthetic-motion-px-min 4 \
  --synthetic-motion-px-max 28 \
  --synthetic-motion-angle-deg-min 210 \
  --synthetic-motion-angle-deg-max 330 \
  --synthetic-center-x-min 0.42 \
  --synthetic-center-x-max 0.58 \
  --synthetic-center-y-min 0.45 \
  --synthetic-center-y-max 0.68 \
  --synthetic-blur-probability 0.35 \
  --output-markdown docs/current/yolo_search_s3h_targeted_synthetic_result_20260705.md
```

## Decision Rule

- If best-recall validation recall exceeds S3d's `0.774`, continue targeted
  synthetic tuning.
- If it does not improve by early epochs, stop and switch to real labeling/hard
  negative review because synthetic-only targeting is insufficient.
- Completion still requires verified recall above `0.90`.
