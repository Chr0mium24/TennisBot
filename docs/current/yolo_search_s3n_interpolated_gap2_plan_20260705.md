# Search-S3n Gap2 Interpolated Pseudo Plan - 2026-07-05

## Goal

Continue toward verified recall above `0.90` with stricter generated-data
quality control after S3m failed.

## Evidence From S3m

S3m generated `751` interpolation labels with `max_frame_gap=5`, then trained a
temporal heatmap model on that expanded label root. It reached only:

- best recall: `0.710`
- precision at best recall: `0.262`

That is worse than S3d's `0.774` recall. The likely issue is label quality:
longer interpolation spans can drift from the actual ball, and direct training
on all generated labels gives them full positive weight.

## S3n Change

Use the same interpolation tool but only accept the shortest possible gaps:

- `max_frame_gap=2`
- generated labels expected: `126`
- cam1/cam2 expected split: about `72/54`

This creates at most one interpolated frame between two adjacent positive
anchors. It is a smaller generated dataset than S3m, but should have lower
trajectory drift.

## Commands

Generate labels:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap interpolate-labels \
  --base-labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --name s3c_pseudo_interp_gap2_20260705 \
  --max-frame-gap 2 \
  --exclude 20260701_155008 \
  --output-markdown docs/current/yolo_search_s3n_interpolated_gap2_generation_result_20260705.md \
  --overwrite
```

Train:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3n_temporal_heatmap_w5_960x540_interp_gap2_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_interpolated_labels/s3c_pseudo_interp_gap2_20260705/labels \
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
  --output-markdown docs/current/yolo_search_s3n_interpolated_gap2_result_20260705.md
```

## Decision Gate

- Continue only if early recall approaches or exceeds S3d's `0.774`.
- If S3n also stays below S3d, interpolation-based generated labels should not
  be scaled further without review or source weighting.
