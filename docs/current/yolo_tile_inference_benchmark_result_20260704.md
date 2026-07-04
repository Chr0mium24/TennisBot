# YOLO Tile Random Input Benchmark Result - 2026-07-04

## Scope

This benchmark uses the current YOLO model with random uint8 image inputs.
It does not use camera capture, real images, stereo matching, or trajectory code.
The timing is intended to compare tile size and `imgsz` cost for first-pass recognition experiments.

## Settings

- Model: `/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo/model.pt`
- Frame: `3840x2160`
- Warmup iterations: `2`
- Timed iterations: `6`
- Device argument: `0`
- CUDA available: `True`
- Device name: `NVIDIA GeForce RTX 4060 Ti`
- Torch: `2.12.1+cu130`

## Results

| profile | tile | overlap | imgsz | tiles/cam | sources/stereo | model MPix | crop MPix | median ms | p95 ms | FPS | CUDA MB | status |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| full_4k | 3840x2160 | 0 | 960 | 1 (1x1) | 2 | 1.84 | 16.59 | 12.0 | 13.9 | 83.00 | 101 | ok |
| full_4k | 3840x2160 | 0 | 1280 | 1 (1x1) | 2 | 3.28 | 16.59 | 17.9 | 20.0 | 55.79 | 150 | ok |
| full_4k | 3840x2160 | 0 | 1536 | 1 (1x1) | 2 | 4.72 | 16.59 | 28.1 | 30.4 | 35.63 | 193 | ok |
| tile_2048x1216 | 2048x1216 | 160 | 960 | 4 (2x2) | 8 | 7.37 | 19.92 | 42.6 | 48.6 | 23.45 | 170 | ok |
| tile_2048x1216 | 2048x1216 | 160 | 1280 | 4 (2x2) | 8 | 13.11 | 19.92 | 75.7 | 80.0 | 13.22 | 268 | ok |
| tile_2048x1216 | 2048x1216 | 160 | 1536 | 4 (2x2) | 8 | 18.87 | 19.92 | 118.3 | 123.3 | 8.45 | 372 | ok |
| tile_2048x1152 | 2048x1152 | 160 | 960 | 6 (2x3) | 12 | 11.06 | 28.31 | 56.4 | 56.8 | 17.72 | 221 | ok |
| tile_2048x1152 | 2048x1152 | 160 | 1280 | 6 (2x3) | 12 | 19.66 | 28.31 | 103.6 | 103.8 | 9.65 | 366 | ok |
| tile_2048x1152 | 2048x1152 | 160 | 1536 | 6 (2x3) | 12 | 28.31 | 28.31 | 148.1 | 152.1 | 6.75 | 500 | ok |
| tile_1536x864 | 1536x864 | 160 | 960 | 9 (3x3) | 18 | 16.59 | 23.89 | 86.2 | 86.9 | 11.60 | 312 | ok |
| tile_1536x864 | 1536x864 | 160 | 1280 | 9 (3x3) | 18 | 29.49 | 23.89 | 168.8 | 172.2 | 5.92 | 530 | ok |
| tile_1536x864 | 1536x864 | 160 | 1536 | 9 (3x3) | 18 | 42.47 | 23.89 | 245.1 | 258.9 | 4.08 | 726 | ok |

## Initial Readout

- `2048x1216 + imgsz=1280` is the best first-pass speed/scale compromise from this run: `13.22` FPS for one stereo frame.
- `1536x864 + imgsz=1280` is much more expensive: `5.92` FPS, about `2.2x` slower than `2048x1216 + imgsz=1280`.
- `1536x864 + imgsz=960` is a useful intermediate test point: `11.60` FPS, with more tile detail than full-frame but lower model input cost than `imgsz=1280`.
- `1536x864 + imgsz=1536` is not a good first test unless recall at lower `imgsz` is clearly inadequate: `4.08` FPS.
- `2048x1152` should not be used as the fast fallback with the current tiler. It becomes `2x3` tiles per camera, while `2048x1216` stays `2x2`.

## Notes

- `tiles/cam` is computed with the same current tiling math as the runtime tools.
- `sources/stereo` is the number of image inputs processed for one left+right stereo frame.
- `model MPix` is `sources/stereo * imgsz * imgsz`, a useful proxy for GPU model cost.
- `crop MPix` is the total tile image area fed to preprocessing for one stereo frame.
- `FPS` is `1000 / median_ms` for one stereo frame under this benchmark.
