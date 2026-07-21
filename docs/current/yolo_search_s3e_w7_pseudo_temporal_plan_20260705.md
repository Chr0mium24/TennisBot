# Search-S3e W7 Pseudo Temporal Heatmap Plan - 2026-07-05

## Goal

Train a separate high-recall search teacher before spending more time on
runtime integration or larger pseudo-label mining.

S3d improved held-out recall to `0.774`, but precision dropped because the
pseudo labels are noisy. S3e keeps the same pseudo-label root so the data
baseline is comparable, then changes the temporal model configuration to test
whether more motion context can recover additional small/blurred ball cases.

## Model Variant

- Model family: temporal heatmap search teacher.
- Input: `7` RGB frames instead of `5`.
- Resolution: `960x540`.
- Heatmap sigma: `5.0` px.
- Validation match radius: `14` px.
- Positive loss weight: `100`.
- Synthetic positives: `1000`.

This is still an offline teacher experiment. It is not a CPU runtime model and
does not validate real ROS/chassis, stereo triangulation, target prediction, or
chassis control.

## Data

- Images root: `tools/yolo/workspace/dataset/images`.
- Labels root:
  `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`.
- Validation token: `20260701_155008`.
- Training excludes validation token.

The held-out validation set remains real labels only. Pseudo labels are used
only on non-validation windows.

## Training Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3e_temporal_heatmap_w7_960x540_pseudo989_synth1000_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --device cuda:0 \
  --epochs 50 \
  --patience 14 \
  --batch 3 \
  --workers 4 \
  --input-width 960 \
  --input-height 540 \
  --window 7 \
  --sigma 5.0 \
  --radius-px 14 \
  --max-negative-ratio 1.5 \
  --synthetic-count 1000 \
  --synthetic-motion-px-max 24 \
  --positive-weight 100 \
  --thresholds 0.02,0.03,0.05,0.08,0.10,0.15,0.20,0.30,0.40,0.50,0.60,0.70 \
  --seed 20260705 \
  --output-markdown docs/current/yolo_search_s3e_w7_pseudo_temporal_result_20260705.md
```

## Decision Rule

- If best-recall validation recall reaches `>0.90`, audit false positives and
  visualize misses before considering it a teacher candidate.
- If recall improves but remains below `0.90`, keep S3e as evidence that longer
  temporal context helps, then clean/minimize pseudo-label noise.
- If recall regresses, stop changing the teacher architecture and spend the
  next iteration on label quality and miss-case review.
