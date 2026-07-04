# Search-S3g Track Top3000 Temporal Plan - 2026-07-05

## Goal

Continue toward `>0.90` held-out recall using more data than S3d, while
avoiding the full S3f pseudo-label set that regressed at epoch 1.

S3f full track-pseudo training was stopped after epoch 1:

- recall: `0.667`
- precision: `0.245`
- best-recall selection: `0.667 @ 0.05`

The full `7503` pseudo-label set is too heavy and likely still noisy. S3g keeps
the same temporal consistency rules, but writes only the top-score accepted
track candidates.

## Mining Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap mine-pseudo \
  --checkpoint tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt \
  --name s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705 \
  --threshold 0.70 \
  --min-track-length 3 \
  --max-frame-gap 1 \
  --max-motion-px 48 \
  --max-pseudo 3000 \
  --batch 8 \
  --workers 4 \
  --device cuda:0 \
  --output-markdown docs/current/yolo_search_s3g_track_top3000_mining_result_20260705.md
```

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3g_temporal_heatmap_w5_960x540_tracktop3000_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_top3000_thr070_len3_gap1_motion48_20260705/labels \
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
  --synthetic-count 500 \
  --synthetic-motion-px-max 20 \
  --output-markdown docs/current/yolo_search_s3g_track_top3000_temporal_result_20260705.md
```

## Decision Rule

- Continue only if early validation recall approaches or exceeds S3d's `0.774`.
- If top3000 still regresses, pseudo-label self-training is not clean enough;
  inspect tracks visually or add real labels before another training run.
