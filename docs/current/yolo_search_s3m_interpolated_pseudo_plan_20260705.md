# Search-S3m Interpolated Pseudo Temporal Plan - 2026-07-05

## Goal

Continue toward verified held-out recall above `0.90` by generating more
real-frame positive labels without scaling the noisy full self-training set.

## Current Evidence

- Best single model remains S3d:
  - recall `0.774`
  - TP `72`, FN `21`
- S3e/S3j/S3k/S3l did not beat S3d.
- A checkpoint-union check across S3d, S3e, S3j, S3k, and S3l did not improve
  recall. The union stayed at `0.774`, so these variants miss the same held-out
  positives.
- Full track-pseudo self-training produced `7503` pseudo labels and regressed.
- Top3000 pseudo self-training also stayed below S3d.

## Data Generation Strategy

Generate labels only between adjacent positive anchors in the same non-held-out
sequence:

1. Start from S3c's high-confidence pseudo label root:
   `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`.
2. Exclude validation token `20260701_155008`.
3. For each sequence, find adjacent positive label frames.
4. If the frame gap is at most `5`, linearly interpolate center and box size
   for missing or empty intermediate label files.
5. Keep existing positives unchanged.

The preflight count for `max_gap=5` is approximately:

| source root | generated labels | cam1 | cam2 |
|---|---:|---:|---:|
| S3c pseudo root | 751 | 395 | 356 |

This is intentionally more conservative than the failed `7503` full
self-training set. It adds temporal density around already accepted tracks
instead of accepting isolated model peaks.

## Commands

Generate interpolated labels:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap interpolate-labels \
  --base-labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --name s3c_pseudo_interp_gap5_20260705 \
  --max-frame-gap 5 \
  --exclude 20260701_155008 \
  --output-markdown docs/current/yolo_search_s3m_interpolated_pseudo_generation_result_20260705.md \
  --overwrite
```

Train S3m:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3m_temporal_heatmap_w5_960x540_interp_gap5_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels \
  --window 5 \
  --input-width 960 \
  --input-height 540 \
  --sigma 4.0 \
  --radius-px 12 \
  --max-negative-ratio 1.5 \
  --synthetic-count 500 \
  --epochs 45 \
  --patience 8 \
  --batch 4 \
  --workers 4 \
  --device cuda:0 \
  --positive-weight 80 \
  --latency-repeats 30 \
  --seed 20260705 \
  --output-markdown docs/current/yolo_search_s3m_interpolated_pseudo_result_20260705.md
```

## Decision Gate

- Continue if S3m exceeds S3d's `0.774` recall.
- Strong target remains recall above `0.90`.
- If S3m does not beat S3d, the automatic generated-data path is effectively
  exhausted; remaining progress requires reviewed real positives or a
  fundamentally different localization objective.
