# Small YOLO vs Small Heatmap Plan - 2026-07-06

## Goal

Compare a small/full-frame YOLO search baseline against a low-resolution heatmap search student on the same held-out continuous sequence.

## Baselines Already Measured

Dataset:

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

YOLO full-frame search results from `docs/current/yolo_fullscreen_155008_search_compare_20260706.md`:

| model | input | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|
| old YOLO | full-frame imgsz 320 | 0.226 | 0.029 | 4.17 | 119.79 |
| old YOLO | full-frame imgsz 416 | 0.290 | 0.060 | 4.39 | 113.94 |
| old YOLO | full-frame imgsz 512 | 0.333 | 0.088 | 4.65 | 107.56 |
| old YOLO | full-frame imgsz 640 | 0.398 | 0.068 | 5.17 | 96.78 |

## Heatmap Student Experiment

Train a lower-resolution heatmap model using the same expanded S3d label root:

- Labels root: `tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`
- Held-out validation token: `20260701_155008`
- Window: `5`
- Input: `480x270`
- Sigma: `2.0`
- Hit radius: `6px`
- Synthetic positives: `500`
- Compare against the YOLO full-frame rows above.

## Command

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo temporal-heatmap train \
  --name search_small_heatmap_w5_480x270_pseudo989_synth500_20260706 \
  --labels-root tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels \
  --window 5 \
  --input-width 480 \
  --input-height 270 \
  --sigma 2.0 \
  --radius-px 6 \
  --synthetic-count 500 \
  --epochs 30 \
  --patience 8 \
  --batch 8 \
  --workers 2 \
  --device auto \
  --thresholds 0.05,0.10,0.15,0.20,0.30,0.40,0.50,0.60,0.70 \
  --latency-repeats 30 \
  --output-markdown docs/current/small_heatmap_w5_480x270_result_20260706.md
```

## Decision Rule

The small heatmap path is only worth continuing if it beats YOLO full-frame recall by a useful margin while staying much faster than current S3d.

Minimum bar:

- recall higher than YOLO full-frame `640` recall `0.398`;
- estimated stereo FPS materially better than current S3d chain `~5 FPS`;
- false positives low enough that ROI confirmation is plausible.
