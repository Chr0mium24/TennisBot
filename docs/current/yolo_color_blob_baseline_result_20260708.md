# YOLO Color Blob Baseline Result - 2026-07-08

## Scope

This records a non-YOLO classical color/blob baseline for tiny fixed-exposure
balls. It was run as a quick check after tiny copy-paste failed to recover
`4-8 px` small targets. It does not validate stereo triangulation,
trajectory prediction, ROS/Gazebo, or chassis control.

## Reason

The detector still fails on fixed-exposure small targets:

- full-frame `imgsz=1536` after tiny copy-paste: small recall `0.080`
- oracle `1024x576` ROI: small recall about `0.52`

The next question was whether tiny fixed balls have a simple color/brightness
signature that a classical blob detector can catch.

## Method

I first inspected HSV/BGR statistics on fixed-exposure `train_pool` and
`benchmark` labels. The benchmark small balls are low-saturation green/yellow
points, but their appearance does not match the train-pool small distribution
well.

Then I tested four hand-picked HSV/blob candidates on the frozen final raw
benchmark. Each candidate:

- thresholds HSV and `G-R`;
- runs connected components;
- filters by component area, width/height, aspect ratio;
- expands the component bbox by a small padding;
- reports those bboxes through the same final raw benchmark matcher.

This is not a tuned production detector. It is a sanity check for whether a
simple traditional baseline has enough signal to justify further work.

## Benchmark Results

Benchmark:
`tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl`

| candidate | overall R/P | fixed R/P | small R/P | medium R/P | large R/P | empty FP imgs | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|
| bright_small | 0.014 / 0.000 | 0.013 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.028 / 0.000 | 91 | 10.3 |
| bench_small_like | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 91 | 10.1 |
| low_sat_bright | 0.062 / 0.000 | 0.004 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.127 / 0.001 | 91 | 9.9 |
| tiny_only | 0.003 / 0.000 | 0.004 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 0.007 / 0.000 | 91 | 10.2 |

## Readout

This route is not useful in its current form.

- Fixed small recall stayed at `0.000` for all candidates.
- False positives exploded: the candidates generated tens of thousands of
  boxes across 381 images, and nearly every empty image fired.
- Runtime was also poor because full-frame connected components over noisy
  masks costs far more than YOLO inference in this setup.

The failure mode is not just a bad confidence threshold. Even with many
candidates per image, the thresholded blobs do not align with the small-ball
labels. A simple HSV/blob detector should not be the next main path.

Next useful work should focus on one of:

- a high-resolution or smaller-stride learned detector head;
- a heatmap/keypoint model trained on ball centers;
- more real fixed-exposure `4-8 px` labels;
- temporal evidence across consecutive frames.

