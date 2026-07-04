# Search-S3f Track-Filtered Pseudo Temporal Plan - 2026-07-05

## Goal

Continue toward held-out validation recall above `0.90` by adding more useful
training data without repeating the noisy pseudo-label failure from S3d/S3e.

Current best checkpoint:

- S3d best recall: `0.774`
- S3d precision at best recall: `0.327`
- S3e best recall: `0.753`

S3e showed that simply increasing temporal window length is not enough. The
next experiment should improve label quality and quantity.

## Data Strategy

Mine pseudo labels from non-validation continuous image sequences using the S3d
`best_recall.pt` checkpoint, but require temporal consistency before writing a
label:

- score threshold: `0.70`
- minimum track length: `3` consecutive candidate frames
- max frame gap: `1`
- max input-scale motion: `48` px/frame
- validation token excluded: `20260701_155008`
- base labels are copied first, pseudo labels only fill empty/missing label
  files

This should reduce isolated false positives compared with the earlier random
single-window pseudo-label run.

## Mining Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap mine-pseudo \
  --checkpoint tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt \
  --name s3d_best_recall_track_thr070_len3_gap1_motion48_20260705 \
  --threshold 0.70 \
  --min-track-length 3 \
  --max-frame-gap 1 \
  --max-motion-px 48 \
  --batch 8 \
  --workers 4 \
  --device cuda:0 \
  --output-markdown docs/current/yolo_search_s3f_track_pseudo_mining_result_20260705.md
```

## Training Command

After mining, train S3f from the new labels root:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3f_temporal_heatmap_w5_960x540_trackpseudo_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3d_best_recall_track_thr070_len3_gap1_motion48_20260705/labels \
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
  --output-markdown docs/current/yolo_search_s3f_track_pseudo_temporal_result_20260705.md
```

## Decision Rule

- If S3f reaches `>0.90` recall, audit false positives and misses before
  calling the goal complete.
- If recall improves but remains below `0.90`, keep the cleaner pseudo-label
  root and mine/review more tracks.
- If recall regresses, inspect candidate tracks visually and tighten pseudo
  mining before training again.
