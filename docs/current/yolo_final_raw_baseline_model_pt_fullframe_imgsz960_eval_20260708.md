# YOLO Final Raw Benchmark Eval - 2026-07-08

## Scope

This evaluates a YOLO detector on the frozen raw-image benchmark manifest.
It reports detection metrics by dataset and target-size bucket.
It does not validate stereo triangulation, trajectory prediction, real ROS/chassis, or chassis control.

## Settings

- Model: `artifacts/models/tennis_ball_yolo/model.pt`
- Manifest: `tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl`
- Split: `benchmark`
- Images: `381`
- Dataset counts: `{"auto_exposure": 72, "fixed_exposure": 309}`
- Bucket counts: `{"empty": 92, "large": 142, "medium": 35, "small": 112}`
- YOLO imgsz: `960`
- Confidence thresholds: `0.050,0.250`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Max detections: `300`
- Device argument: `0`
- CUDA available: `True`
- Torch: `2.11.0+cu128`

## Results

| conf | dataset | bucket | images | pos imgs | gt | TP | FP | FN | recall | precision | empty FP imgs | median ms/img | p95 ms/img | mono FPS | est stereo FPS |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.050 | all | all | 381 | 289 | 289 | 86 | 266 | 203 | 0.298 | 0.244 | 45 | 3.56 | 3.64 | 280.91 | 140.46 |
| 0.050 | auto_exposure | all | 72 | 66 | 66 | 54 | 124 | 12 | 0.818 | 0.303 | 5 | 3.22 | 3.26 | 310.96 | 155.48 |
| 0.050 | fixed_exposure | all | 309 | 223 | 223 | 32 | 142 | 191 | 0.143 | 0.184 | 40 | 3.57 | 3.64 | 280.23 | 140.11 |
| 0.050 | all | small | 112 | 112 | 112 | 3 | 58 | 109 | 0.027 | 0.049 | 0 | 3.57 | 3.64 | 280.28 | 140.14 |
| 0.050 | all | medium | 35 | 35 | 35 | 3 | 1 | 32 | 0.086 | 0.750 | 0 | 3.55 | 3.60 | 281.35 | 140.67 |
| 0.050 | all | large | 142 | 142 | 142 | 80 | 115 | 62 | 0.563 | 0.410 | 0 | 3.54 | 3.63 | 282.58 | 141.29 |
| 0.050 | all | empty | 92 | 0 | 0 | 0 | 92 | 0 | n/a | 0.000 | 45 | 3.57 | 3.64 | 279.81 | 139.91 |
| 0.050 | auto_exposure | large | 66 | 66 | 66 | 54 | 111 | 12 | 0.818 | 0.327 | 0 | 3.22 | 3.25 | 310.96 | 155.48 |
| 0.050 | auto_exposure | empty | 6 | 0 | 0 | 0 | 13 | 0 | n/a | 0.000 | 5 | 3.22 | 10.37 | 310.90 | 155.45 |
| 0.050 | fixed_exposure | small | 112 | 112 | 112 | 3 | 58 | 109 | 0.027 | 0.049 | 0 | 3.57 | 3.64 | 280.28 | 140.14 |
| 0.050 | fixed_exposure | medium | 35 | 35 | 35 | 3 | 1 | 32 | 0.086 | 0.750 | 0 | 3.55 | 3.60 | 281.35 | 140.67 |
| 0.050 | fixed_exposure | large | 76 | 76 | 76 | 26 | 4 | 50 | 0.342 | 0.867 | 0 | 3.57 | 3.64 | 279.96 | 139.98 |
| 0.050 | fixed_exposure | empty | 86 | 0 | 0 | 0 | 79 | 0 | n/a | 0.000 | 40 | 3.58 | 3.64 | 279.67 | 139.83 |
| 0.250 | all | all | 381 | 289 | 289 | 54 | 100 | 235 | 0.187 | 0.351 | 29 | 3.56 | 3.64 | 280.91 | 140.46 |
| 0.250 | auto_exposure | all | 72 | 66 | 66 | 38 | 73 | 28 | 0.576 | 0.342 | 5 | 3.22 | 3.26 | 310.96 | 155.48 |
| 0.250 | fixed_exposure | all | 309 | 223 | 223 | 16 | 27 | 207 | 0.072 | 0.372 | 24 | 3.57 | 3.64 | 280.23 | 140.11 |
| 0.250 | all | small | 112 | 112 | 112 | 0 | 0 | 112 | 0.000 | n/a | 0 | 3.57 | 3.64 | 280.28 | 140.14 |
| 0.250 | all | medium | 35 | 35 | 35 | 1 | 0 | 34 | 0.029 | 1.000 | 0 | 3.55 | 3.60 | 281.35 | 140.67 |
| 0.250 | all | large | 142 | 142 | 142 | 53 | 67 | 89 | 0.373 | 0.442 | 0 | 3.54 | 3.63 | 282.58 | 141.29 |
| 0.250 | all | empty | 92 | 0 | 0 | 0 | 33 | 0 | n/a | 0.000 | 29 | 3.57 | 3.64 | 279.81 | 139.91 |
| 0.250 | auto_exposure | large | 66 | 66 | 66 | 38 | 67 | 28 | 0.576 | 0.362 | 0 | 3.22 | 3.25 | 310.96 | 155.48 |
| 0.250 | auto_exposure | empty | 6 | 0 | 0 | 0 | 6 | 0 | n/a | 0.000 | 5 | 3.22 | 10.37 | 310.90 | 155.45 |
| 0.250 | fixed_exposure | small | 112 | 112 | 112 | 0 | 0 | 112 | 0.000 | n/a | 0 | 3.57 | 3.64 | 280.28 | 140.14 |
| 0.250 | fixed_exposure | medium | 35 | 35 | 35 | 1 | 0 | 34 | 0.029 | 1.000 | 0 | 3.55 | 3.60 | 281.35 | 140.67 |
| 0.250 | fixed_exposure | large | 76 | 76 | 76 | 15 | 0 | 61 | 0.197 | 1.000 | 0 | 3.57 | 3.64 | 279.96 | 139.98 |
| 0.250 | fixed_exposure | empty | 86 | 0 | 0 | 0 | 27 | 0 | n/a | 0.000 | 24 | 3.58 | 3.64 | 279.67 | 139.83 |

## Timing Notes

- Predictions are run once at the lowest confidence threshold, then filtered for higher thresholds.
- `mono FPS` is `1000 / median_ms_per_image` on this offline replay.
- `est stereo FPS` assumes left and right camera images are processed sequentially at the same median cost.

## Run Notes

- This is the current packaged baseline model, `artifacts/models/tennis_ball_yolo/model.pt`, not a model retrained from the v1 `train_pool`.
- The training machine did not have the original fixed-exposure source paths, so the remote eval manifest remapped fixed-exposure rows to the equivalent `fixed__...` raw files inside `fixed_exposure_traditional_roi_3000_20260707`. Auto-exposure original images were synced to the expected raw path. The split, labels, buckets, and benchmark membership were not changed.
- CUDA eval used `/home/anilam/Downloads/vision/yolo_training/.venv` because the project `.venv` currently resolves to Python 3.14 with `torch-2.12.1+cu130`, which is incompatible with the installed NVIDIA driver. The working eval environment reports `torch-2.11.0+cu128` and CUDA available.

## Readout

This baseline is fast enough but not accurate enough.

- Speed is above the target: full-frame `imgsz=960` is about `3.56 ms/img`, or `140.46` estimated stereo FPS overall.
- Low-threshold recall is only `0.298` overall and `0.143` on fixed exposure.
- The small and medium buckets are effectively failing: `small` recall is `0.027`, `medium` recall is `0.086` at `conf=0.05`.
- Raising confidence to `0.25` reduces false positives but drops overall recall to `0.187` and fixed-exposure recall to `0.072`.
- Empty-frame false positives are still high: `45` empty images fire at `conf=0.05`, and `29` still fire at `conf=0.25`.

The next training pass should not optimize FPS first. The detector has enough
runtime headroom; the missing work is fixed-exposure/small-target recall and
empty-frame precision, using only v1 `train_pool` sources.
