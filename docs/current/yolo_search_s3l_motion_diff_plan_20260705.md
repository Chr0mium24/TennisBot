# Search-S3l Motion-Diff Temporal Heatmap Plan - 2026-07-05

## Goal

Train a second search/acquisition model before more data generation. This run
tests whether explicit motion cues improve the current best S3d temporal
heatmap teacher on the same held-out continuous sequence.

## Research Basis

- WASB frames sports ball detection as heatmap prediction with high-resolution
  feature extraction, position-aware training, and temporal consistency:
  <https://github.com/nttcom/WASB-SBDT> and
  <https://papers.bmvc2023.org/0310.pdf>.
- TrackNet uses multiple consecutive frames and Gaussian heatmaps for small,
  blurry tennis balls:
  <https://github.com/yastrebksv/TrackNet>.
- TrackNetV4 reports that fusing visual features with frame-difference motion
  attention helps high-speed small sports-object tracking under low visibility:
  <https://arxiv.org/abs/2409.14543>.
- The AIS-Bonn temporal ball detector is another official example of using
  sequence-level temporal information for ball detection:
  <https://github.com/AIS-Bonn/TemporalBallDetection>.

The useful next local variant is therefore not another plain detector. It is a
temporal heatmap model with an explicit frame-difference input path.

## Model Change

Baseline S3d input:

- `5` RGB frames concatenated as `15` input channels.

S3l input:

- the same `5` RGB frames;
- plus `4` grayscale absolute-difference maps between adjacent frames;
- total `19` input channels.

The network body, loss, validation sequence, resolution, synthetic count, and
pseudo-label root stay aligned with S3d so the comparison isolates the input
representation.

## Training Data

- Images root: `tools/yolo/workspace/dataset/images`
- Labels root:
  `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Validation token: `20260701_155008`
- Train excludes validation token.
- Synthetic positives: `500`, matching S3d.

This does not use held-out labels for training.

## Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_s3l_temporal_heatmap_w5_960x540_rgbdiff_pseudo989_synth500_20260705 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --window 5 \
  --input-width 960 \
  --input-height 540 \
  --input-mode rgb-diff \
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
  --output-markdown docs/current/yolo_search_s3l_motion_diff_result_20260705.md
```

## Promotion Criteria

- Primary: best-recall checkpoint exceeds S3d held-out recall `0.774`.
- Strong target: recall approaches or exceeds `0.90`.
- Latency must remain measured separately; training can improve recall but does
  not itself guarantee runtime FPS.

If S3l does not beat S3d, the next useful action is not more unreviewed
synthetic or self-labeled data. The miss audit already shows the remaining
errors are mostly wrong-peak localization, so reviewed real positives around
held-out-like net/center failures become the bottleneck.
