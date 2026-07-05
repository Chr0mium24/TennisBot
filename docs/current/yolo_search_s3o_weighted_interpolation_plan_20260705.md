# Search-S3o Weighted Interpolation Plan - 2026-07-05

## Goal

Continue toward verified recall above `0.90` by using generated interpolation
labels as weak supervision instead of full-strength positives.

## Evidence

- S3d remains best: recall `0.774`.
- S3m used `751` gap5 interpolated labels at full training weight and reached
  only `0.710` recall.
- S3n used stricter `126` gap2 labels at full weight and reached only `0.699`
  recall.

The problem may be not just generated-label quality, but also that generated
labels are treated as equally reliable as original/pseudo anchor labels.

## Change

Train on the S3m gap5 label root but downweight the interpolated samples:

- label root:
  `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels`
- generated-label manifest:
  `tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/manifest.csv`
- manifest sample weight: `0.25`

All other settings match S3d/S3m as closely as possible.

## Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3o_temporal_heatmap_w5_960x540_interp_gap5_w025_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/labels \
  --sample-weight-manifest tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap5_20260705/manifest.csv \
  --manifest-sample-weight 0.25 \
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
  --output-markdown docs/current/yolo_search_s3o_weighted_interpolation_result_20260705.md
```

## Decision Gate

- Continue only if S3o approaches or exceeds S3d's `0.774` recall early.
- If S3o stays below S3d, generated interpolation labels are not useful even as
  low-weight weak supervision, and the next data work should be reviewed real
  positives for the held-out-like net/center miss pattern.
