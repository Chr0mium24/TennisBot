# Small YOLO vs Small Heatmap Result - 2026-07-06

## Scope

This compares the current full-frame YOLO search baseline against a newly trained low-resolution temporal heatmap student.

This is an offline detector/search comparison only. It does not validate real ROS/chassis, stereo triangulation, target prediction, or chassis control.

## User Concern

`480x270` can absolutely lose small-ball image detail. This experiment does not prove `480x270` is the final input size.

The purpose was narrower: test whether a small heatmap search student still has better recall than small full-frame YOLO under similar runtime cost.

## Data

Held-out validation:

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

Validation positives: `93`

Training labels for heatmap:

`tools/yolo/workspace/runs/temporal_pseudo_labels/s3c_best_thr070_sample3000_20260705/labels`

## Small YOLO Baseline

From `docs/current/yolo_fullscreen_155008_search_compare_20260706.md`.

| model | input | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| old YOLO | full-frame imgsz 320 | 21 | 694 | 72 | 0.226 | 0.029 | 4.17 | 119.79 |
| old YOLO | full-frame imgsz 416 | 27 | 424 | 66 | 0.290 | 0.060 | 4.39 | 113.94 |
| old YOLO | full-frame imgsz 512 | 31 | 321 | 62 | 0.333 | 0.088 | 4.65 | 107.56 |
| old YOLO | full-frame imgsz 640 | 37 | 509 | 56 | 0.398 | 0.068 | 5.17 | 96.78 |

## Small Heatmap Student

Command:

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

Best validation:

| model | input | epoch | threshold | TP | FP | FN | recall | precision | F1 | mean TP dist px | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| small heatmap | 5xRGB 480x270 | 17 | 0.70 | 67 | 162 | 26 | 0.720 | 0.293 | 0.416 | 0.86 | 4.74 | 105.43 |

Best F1:

| model | input | epoch | threshold | TP | FP | FN | recall | precision | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small heatmap | 5xRGB 480x270 | 19 | 0.70 | 66 | 154 | 27 | 0.710 | 0.300 | 0.422 |

## Readout

The small heatmap student beats the small/full-frame YOLO baseline on recall at similar measured latency:

- best YOLO recall: `0.398` at `imgsz=640`, `5.17ms/img`;
- small heatmap best recall: `0.720` at `480x270`, `4.74ms/img`.

The small heatmap still has too many false positives:

- YOLO `640`: `509` FP, precision `0.068`;
- heatmap `480x270`: `162` FP, precision `0.293`.

Both are still too noisy for a final search model, but heatmap is substantially better on this held-out sequence.

## Information Loss Note

The user concern is correct: a `480x270` input can erase visual detail of a tiny tennis ball.

Why the heatmap can still win here:

- it uses five-frame temporal context, not one static frame;
- the target is a point heatmap instead of a full bbox regression problem;
- validation accepts a coarse center within `6px` at `480x270`, suitable for ROI acquisition rather than final localization.

This does not mean `480x270` is safe for all scenes. It means low-resolution temporal heatmap is worth exploring as a runtime search student.

## Decision

Continue the heatmap student direction, but do not freeze `480x270` as the final input.

Next fair experiments:

1. Train `640x360` heatmap with the same settings to measure the recall/detail tradeoff.
2. Try `3` frames vs `5` frames to reduce latency and buffering.
3. Add ROI-confirmation metrics so search precision is measured after ROI YOLO, not only by raw heatmap FP.
4. Compare against a real small-YOLO student with P2/tiled input, not only the current old YOLO full-frame model.
