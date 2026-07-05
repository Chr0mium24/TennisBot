# Search-S3j Pseudo + Small Hard-Negative Temporal Plan - 2026-07-05

## Goal

Continue toward held-out recall above `0.90` by combining the best recall data
source so far with a small hard-negative subset.

Current evidence:

- S3d is still the best recall model: `0.774`.
- S3d used `989` pseudo labels plus `500` synthetic positives.
- S3i hard negatives improved precision but reduced recall to `0.677`.

S3j keeps S3d's pseudo-positive base and adds only the top `300` high-score
background hard negatives. The intent is to suppress the dominant distractor
without overwhelming the positive signal.

## Hard-Negative Mining Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap hard-negatives \
  --candidates-csv tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/candidates.csv \
  --base-labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --name s3d_left_bg_hardneg300_on_s3c_pseudo_thr095_x10_40_y25_75_20260705 \
  --threshold 0.95 \
  --x-min 0.10 \
  --x-max 0.40 \
  --y-min 0.25 \
  --y-max 0.75 \
  --max-count 300 \
  --input-width 960 \
  --input-height 540 \
  --output-markdown docs/current/yolo_search_s3j_pseudo_small_hardneg_mining_result_20260705.md
```

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3j_temporal_heatmap_w5_960x540_pseudo_hardneg300_synth500_20260705 \
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
  --synthetic-count 500 \
  --synthetic-motion-px-max 20 \
  --output-markdown docs/current/yolo_search_s3j_pseudo_small_hardneg_temporal_result_20260705.md
```

## Decision Rule

- If S3j exceeds S3d recall `0.774`, continue tuning hard-negative count.
- If recall stays below S3d, the remaining gap needs reviewed real positive
  labels instead of more unreviewed synthetic/hard-negative data.
- Completion still requires verified recall above `0.90`.
