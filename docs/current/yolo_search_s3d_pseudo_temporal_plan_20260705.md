# Search-S3d Pseudo-Label Temporal Heatmap Plan - 2026-07-05

## Goal

Continue toward validation recall above 90%.

Search-S3c with 500 synthetic positives improved the held-out `155008` result:

- best-F1 checkpoint recall: `0.667`;
- highest observed recall during training: `0.731`;
- post-hoc recall selection on saved `best.pt`: `0.699`.

This is progress but still below the requested `>0.90` recall.

## New Data

Use Search-S3c best-F1 checkpoint to mine real-frame pseudo labels:

- checkpoint: `search_s3c_temporal_heatmap_w5_960x540_synth500_20260705/best.pt`;
- source windows: random non-validation 5-frame windows;
- sampled candidate windows: `3000`;
- threshold: `0.70`;
- pseudo labels written: `989`;
- validation token excluded: `20260701_155008`;
- labels root:
  `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`.

The pseudo labels are not committed; the run directory is ignored. This document
records how they were generated.

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
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
  --output-markdown docs/current/yolo_search_s3d_pseudo_temporal_result_20260705.md
```

## Decision Rule

- If `best_recall.pt` reaches `>0.90` recall on held-out real labels, audit
  precision and false positives before marking the goal complete.
- If recall improves but remains below `0.90`, expand pseudo-label mining with
  review/filtering and add more real cam2 labels.
- If recall regresses, treat pseudo-label quality as insufficient and tighten
  mining threshold or require temporal consistency.
