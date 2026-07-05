# Search-S3i Hard-Negative Temporal Plan - 2026-07-05

## Goal

Continue toward held-out recall above `0.90` by suppressing the background
distractor peaks that caused S3d bad-localization misses.

S3d miss audit showed:

- recall: `0.774`
- FN low score: `1`
- FN bad localization: `20`
- common wrong peak: left/ceiling/net-side background region

S3h targeted positives improved precision but not recall. S3i adds hard
negative labels for non-validation frames where S3d predicts a high score in
the same distractor region and no positive label exists.

## Hard-Negative Mining Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap hard-negatives \
  --candidates-csv tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/candidates.csv \
  --name s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705 \
  --threshold 0.95 \
  --x-min 0.10 \
  --x-max 0.40 \
  --y-min 0.25 \
  --y-max 0.75 \
  --input-width 960 \
  --input-height 540 \
  --output-markdown docs/current/yolo_search_s3i_hard_negative_mining_result_20260705.md
```

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3i_temporal_heatmap_w5_960x540_hardneg_targeted_synth2500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_hard_negatives/s3d_left_bg_hardneg_thr095_x10_40_y25_75_20260705/labels \
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
  --max-negative-ratio 12 \
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
  --output-markdown docs/current/yolo_search_s3i_hard_negative_temporal_result_20260705.md
```

## Decision Rule

- If S3i exceeds S3d recall `0.774`, continue hard-negative tuning.
- If S3i improves precision but not recall, hard negatives suppress distractors
  but still need real positives for the held-out failure pattern.
- Completion still requires verified recall above `0.90`.
