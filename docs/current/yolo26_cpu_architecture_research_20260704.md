# YOLO26 CPU Architecture Research - 2026-07-04

## Goal

Find a detector path for 4K tennis-ball recognition that can preserve far-ball
fidelity while moving toward CPU edge deployment.

Target requested for this pass:

- no quantization;
- CPU runtime target: `30 FPS` stereo;
- recall target: `0.90`;
- test whether smaller architectures, P2 heads, and non-YOLO26 candidates can
  work on the current 1000-image trial split.

Result: the target was **not reached**. The current data and architecture sweep
do not support training a tiny detector from zero to `0.90` recall, and the
highest-recall pretrained P2 candidate is too slow for the CPU stereo target.

## Sources Checked

- Ultralytics YOLO26 docs: <https://docs.ultralytics.com/models/yolo26>
- Ultralytics YOLO26 end-to-end guide:
  <https://docs.ultralytics.com/guides/end2end-detection>
- FDM-YOLO GitHub repo: <https://github.com/zdw0513-source/FDM-YOLO>
- Improved_YOLOv8s GitHub repo:
  <https://github.com/Username378/Improved_YOLOv8s>
- YOLO-TLP GitHub repo: <https://github.com/irfan112/YOLO-TLP>
- DroneScan-YOLO GitHub repo:
  <https://github.com/yannbellec/dronescan-yolo>
- Local Ultralytics package YAMLs:
  - `tools/yolo/.venv/lib/python3.13/site-packages/ultralytics/cfg/models/26/yolo26.yaml`
  - `tools/yolo/.venv/lib/python3.13/site-packages/ultralytics/cfg/models/26/yolo26-p2.yaml`

## YOLO26 Architecture Readout

Official YOLO26 detection models are different from older YOLOv8/YOLO11-style
runtime in ways that matter for CPU:

- `end2end: True` by default.
- `reg_max: 1`, meaning the head is DFL-free.
- Inference uses the one-to-one head and returns up to `300` detections as
  `[x1, y1, x2, y2, confidence, class_id]`, so normal end-to-end inference does
  not need external NMS.
- During training there is also a one-to-many head for learning signal. Fusing
  the model removes training-only auxiliary parts.

Official local YAML structure:

| Model | Detect strides | Params | GFLOPs in YAML comment | Notes |
|---|---:|---:|---:|---|
| `yolo26n.yaml` | 8, 16, 32 | 2,572,280 | 6.1 | Standard P3/P4/P5 detector |
| `yolo26n-p2.yaml` | 4, 8, 16, 32 | 2,662,400 | 9.5 | Adds P2/stride-4 small-object head |

Ultralytics documents that P2/P6 variants are shipped as YAML architectures only;
there are no scale-specific `yolo26*-p2.pt` weights. That matters here because a
P2 model must be trained from scratch unless we build our own transfer or
distillation path.

## Project Detection Need

Existing local data inventory from the edge fidelity probe:

- Raw images: `17,900`.
- Label files: `1,222`.
- Matched labeled images: `693`.
- Matched positive images: `302`.
- Matched boxes: `302`.
- Empty matched labels: `391`.
- Boxes with max side `<= 16px`: `101 / 302`.
- Boxes with max side `<= 10px`: `36 / 302`.

This is a real tiny-object problem. On full 4K resized to `imgsz=640`, many balls
become only a few model pixels. Lowering `imgsz` improves speed but directly
destroys the signal needed for far balls.

CPU target math:

- `30 FPS` stereo means one left+right pair must finish in `33.3 ms`.
- If left and right are processed sequentially, that is about `16.7 ms` per
  image. If capture, rectification, stereo pairing, tracking, and ROS output are
  included, the detector budget must be lower than that.
- The target board will be slower than this desktop CPU, so a model that barely
  hits `30 FPS` here is not safe.

## Existing Baseline

The current packaged detector is already YOLO26n-like:

| Model | Params | Strides | `reg_max` | End-to-end |
|---|---:|---:|---:|---|
| `artifacts/models/tennis_ball_yolo/model.pt` | 2,504,190 | 8, 16, 32 | 1 | yes |

Previous full-frame CPU probe on the current model:

| Mode | Recall | Precision | Median ms/img | Est stereo FPS |
|---|---:|---:|---:|---:|
| full 4K, `imgsz=640` | 0.778 | 0.347 | 24.8 | 20.13 |
| full 4K, `imgsz=960` | 0.800 | 0.462 | 44.6 | 11.20 |
| full 4K, `imgsz=1280` | 0.822 | 0.343 | 78.9 | 6.34 |
| ONNX Runtime, `imgsz=1280` | 0.844 | 0.336 | 70.8 e2e | 7.06 |

The current model does not hit `30 FPS` and does not hit `0.90` recall. It is
still the best local accuracy baseline so far.

## Tile Readout

Exhaustive tile is not a free win. For one stereo pair:

- full frame uses `2` model inputs;
- `2048x1216` 2x2 tile uses `8` model inputs;
- `1536x864` 3x3 tile uses `18` model inputs.

Existing probe showed exhaustive tile did not beat full-frame at a useful
CPU/FPS point:

| Mode | Recall | Median ms/img | Est stereo FPS |
|---|---:|---:|---:|
| full 4K, `imgsz=640` | 0.778 | 24.8 | 20.13 |
| tile 2048, `imgsz=640` | 0.756 | 82.0 | 6.10 |
| tile 1536, `imgsz=512` | 0.822 | 109.9 | 4.55 |

Tile can still be useful, but it has to be sparse/ROI-gated. Running every tile
every frame increases compute too much.

## Architecture Sweep

Added experimental configs:

- `tools/yolo/configs/tennis_yolo26_micro_p2.yaml`
- `tools/yolo/configs/tennis_yolo26_micro_p2_no_p5.yaml`
- `tools/yolo/configs/tennis_yolo26_tiny_p2_no_p5.yaml`
- `tools/yolo/configs/tennis_yolov8n_p2.yaml`
- `tools/yolo/configs/tennis_yolov8n_ghost_p2.yaml`

Design ideas tested:

- keep YOLO26 end-to-end and DFL-free head path where possible;
- add/keep a P2 stride-4 output for small targets;
- remove P5 on YOLO26 variants to avoid spending head compute on large targets;
- compare against a non-YOLO26 P2 path using `yolov8n.pt` partial transfer;
- screen a GhostConv/C3Ghost P2 YAML, but do not spend training time on it after
  the latency screen showed it was slower than the plain YOLOv8n-P2 candidate.

YAML load and random-tensor CPU screen:

| Model/config | Params | Strides | Median ms @416 | Median ms @512 | Median ms @640 | Notes |
|---|---:|---|---:|---:|---:|---|
| `yolo26n.yaml` | 2,572,280 | 8,16,32 | 21.70 | 26.54 | 35.24 | Stock nano reference |
| `yolo26n-p2.yaml` | 2,662,400 | 4,8,16,32 | 32.39 | 47.59 | 73.36 | Official P2 YAML, no P2 weights |
| `tennis_yolo26_micro_p2.yaml` | 406,680 | 4,8,16,32 | 16.93 | 25.12 | 39.29 | Fastest P2/P5 YOLO26 student |
| `tennis_yolo26_micro_p2_no_p5.yaml` | 310,094 | 4,8,16 | 15.39 | 22.38 | 34.79 | Cheapest YOLO26 P2/P3/P4 head |
| `tennis_yolo26_tiny_p2_no_p5.yaml` | 649,466 | 4,8,16 | 21.29 | 28.63 | 43.66 | More capacity, still no P5 |
| `tennis_yolov8n_p2.yaml` | 2,926,692 | 4,8,16,32 | 35.30 | 49.34 | 71.49 | Pretrained backbone path |
| `tennis_yolov8n_ghost_p2.yaml` | 1,606,492 | 4,8,16,32 | 44.08 | 66.83 | 94.02 | Slower than plain YOLOv8n-P2 here |
| `yolo11n.yaml` | 2,583,160 | 8,16,32 | 26.45 | 36.36 | 51.49 | Non-YOLO26 stock reference |

The random-tensor screen is not a full 4K pipeline benchmark. It was used only to
prune candidates before 30-epoch training.

## Training Runs

Dataset for all completed runs:

- `tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/data.yaml`
- Val images: `163`.
- Epochs: `30`.
- Train image size: `640`.

Completed runs:

| Run | Init | Batch | Params in best checkpoint | Strides | Best recall | Best mAP50 | Best mAP50-95 | Notes |
|---|---|---:|---:|---|---:|---:|---:|---|
| `tennis_yolo26_micro_p2_aug1000_batch32_imgsz640_20260704` | YAML/scratch | 32 | 406,680 | 4,8,16,32 | 0.50000 | 0.53251 | 0.40663 | Fast but recall-starved |
| `tennis_yolo26_micro_p2_no_p5_aug1000_batch32_imgsz640_20260704` | compatible transfer from micro-P2 best | 32 | 310,094 | 4,8,16 | 0.55085 | 0.57782 | 0.43830 | Best YOLO26 student recall |
| `tennis_yolo26_tiny_p2_no_p5_aug1000_batch32_imgsz640_20260704` | mostly scratch | 32 | 649,466 | 4,8,16 | 0.51451 | 0.53500 | 0.42264 | More params did not fix recall |
| `tennis_yolov8n_p2_aug1000_batch8_imgsz640_20260704` | partial `yolov8n.pt` transfer | 8 | 2,926,692 | 4,8,16,32 | 0.65329 | 0.68570 | 0.53769 | Best validation accuracy, slowest trained candidate |

Failed or deferred runs:

- `tennis_yolov8n_p2_aug1000_batch16_imgsz640_20260704` was killed with exit
  code `137` during the first epoch, likely host memory/process pressure. The
  same config completed with `batch=8`.
- `tennis_yolov8n_ghost_p2.yaml` was not trained because the first latency screen
  was worse than the plain YOLOv8n-P2 config.

The from-scratch YOLO26 student family did not get close to `0.90` recall. The
pretrained YOLOv8n-P2 candidate improved validation recall to about `0.65`, but
at a much higher CPU cost.

## CPU Sample Probe

Sample:

- Source: first `60` images from
  `tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/val.txt`.
- Ground-truth boxes found in this sample: `42`.
- Backend: Ultralytics/PyTorch CPU.
- Threads: `10`.
- Confidence: `0.05`.
- Prediction IoU setting: `0.7`.
- Match IoU: `0.5`.

This table was run in one process for same-run comparison across trained
candidates. Absolute medians should be treated as probe numbers; the ranking and
recall/precision tradeoff are the important outputs.

| Model | imgsz | TP | FP | FN | Recall | Precision | Median ms/img | p95 ms/img | Est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| current package | 416 | 23 | 26 | 19 | 0.548 | 0.469 | 30.00 | 37.61 | 16.67 |
| current package | 512 | 24 | 26 | 18 | 0.571 | 0.480 | 32.90 | 40.89 | 15.20 |
| current package | 640 | 33 | 69 | 9 | 0.786 | 0.324 | 38.76 | 42.40 | 12.90 |
| YOLO26 micro-P2 | 416 | 23 | 21 | 19 | 0.548 | 0.523 | 25.73 | 33.08 | 19.43 |
| YOLO26 micro-P2 | 512 | 24 | 28 | 18 | 0.571 | 0.462 | 30.58 | 35.27 | 16.35 |
| YOLO26 micro-P2 | 640 | 24 | 24 | 18 | 0.571 | 0.500 | 33.18 | 40.16 | 15.07 |
| YOLO26 micro-P2 no-P5 | 416 | 24 | 25 | 18 | 0.571 | 0.490 | 25.31 | 28.29 | 19.75 |
| YOLO26 micro-P2 no-P5 | 512 | 24 | 22 | 18 | 0.571 | 0.522 | 27.00 | 34.10 | 18.52 |
| YOLO26 micro-P2 no-P5 | 640 | 25 | 29 | 17 | 0.595 | 0.463 | 34.48 | 39.17 | 14.50 |
| YOLO26 tiny-P2 no-P5 | 416 | 23 | 16 | 19 | 0.548 | 0.590 | 28.90 | 35.61 | 17.30 |
| YOLO26 tiny-P2 no-P5 | 512 | 24 | 15 | 18 | 0.571 | 0.615 | 35.14 | 39.80 | 14.23 |
| YOLO26 tiny-P2 no-P5 | 640 | 24 | 25 | 18 | 0.571 | 0.490 | 38.16 | 41.44 | 13.10 |
| YOLOv8n-P2 | 416 | 24 | 9 | 18 | 0.571 | 0.727 | 36.70 | 44.18 | 13.62 |
| YOLOv8n-P2 | 512 | 27 | 10 | 15 | 0.643 | 0.730 | 39.91 | 43.21 | 12.53 |
| YOLOv8n-P2 | 640 | 27 | 27 | 15 | 0.643 | 0.500 | 56.23 | 62.40 | 8.89 |

Readout:

- No row reaches `0.90` recall.
- No trained candidate reaches `30 FPS` stereo in this full Ultralytics CPU path.
- The current packaged model at `imgsz=640` remains the best sample recall
  result, but it is below the speed target.
- YOLO26 micro/no-P5 variants save parameters but lose recall.
- YOLOv8n-P2 is the strongest trained architecture by validation metrics, but it
  is too slow for the requested CPU stereo budget.

## GitHub Variant Readout

The external variants are useful references, but none should be imported as a
blind fork before the data/runtime bottleneck is fixed:

| Candidate | Relevant idea | Why not promoted in this pass |
|---|---|---|
| FDM-YOLO | multi-scale fusion, attention, small-target UAV focus | RGB/TIR fusion and custom code path do not match this single-RGB tennis setup directly |
| Improved_YOLOv8s / C2f-Faster-EMA style forks | C2f-Faster, EMA, DyHead, slim neck style changes | would require forked modules; local YAML-only P2 already showed data starvation |
| YOLO-TLP | explicitly targets tiny objects below roughly 15 px | repo is useful as a design reference, but not directly aligned with current Ultralytics YOLO26 deployment path |
| DroneScan-YOLO | P2 branch plus tiny-object loss/pruning ideas | promising for later because of P2 and NWD-style loss, but requires custom loss/pruning integration |

The most relevant external idea for the next iteration is not another backbone by
itself. It is a tiny-object loss/crop regime: preserve local pixels and improve
assignment/box learning for very small boxes.

## Answer To "Can We Train From Zero?"

Not for the target. With only `302` matched real positive boxes and many far
balls below `16px`, from-scratch training a tiny detector is data-starved.

Evidence:

- YOLO26 micro-P2 from YAML/scratch stalled at best validation recall `0.50000`.
- Removing P5 improved YOLO26 student recall only to `0.55085`.
- Increasing YOLO26 student width still stayed near `0.51451` best recall.
- A pretrained YOLOv8n-P2 transfer run reached `0.65329` best validation recall,
  which confirms transfer helps, but it still misses `0.90` and is too slow on
  CPU.

The practical path is not "smaller from scratch". It is:

1. Keep a pretrained/current YOLO26n-like model as teacher/base.
2. Collect and label more real 4K far-ball samples.
3. Train tile/ROI-shaped crops so the ball is not crushed by full-frame resize.
4. Add tiny-object assignment/loss ideas only after the crop/data path is stable.
5. Distill or fine-tune a smaller student only after the teacher is strong.

## Recommended Runtime Direction

For CPU, do not use exhaustive tile as the default.

Recommended detector pipeline:

1. Keep 4K capture as the source of truth.
2. Run a cheap full-frame coarse pass, likely `imgsz=416` or `512`.
3. Use temporal tracking/stereo geometry to select one sparse ROI per camera for
   the next frame.
4. Run the ROI at `imgsz=512` or `640`, preserving local ball pixels without
   scanning every tile.
5. Fall back to full-frame when tracking is lost.

This is the only non-quantized path that can plausibly improve both fidelity and
FPS, because it reduces model inputs per stereo frame instead of multiplying
them.

## Recommended Model Direction

Short term:

- Keep the current YOLO26n-like package as the accuracy baseline.
- Do not promote any new sweep candidate as the runtime detector yet.
- Use `tennis_yolo26_micro_p2_no_p5.yaml` only as an experimental student
  architecture.
- Keep `tennis_yolov8n_p2.yaml` as an accuracy reference, not a CPU runtime
  candidate.

Next training experiment:

- Generate a positive-jitter crop dataset from real 4K labels at runtime-like
  crop shapes, for example `1536x864` or `2048x1216`.
- Fine-tune the current package model at `imgsz=640` and `960`.
- Validate on real far-ball frames and on sparse ROI crops.
- Only after recall improves, distill to a small YOLO26 student.

If a P2 model is still needed:

- Try official `yolo26n-p2.yaml` only after a transfer/distillation path exists.
- Training official P2 from scratch may improve capacity over micro-P2, but it
  adds compute and still lacks pretrained P2 weights.
- Consider a DroneScan-style tiny-object loss only as a controlled code change,
  not as a wholesale fork.

## Decision

The requested target is not achieved in this pass.

- `30 FPS` stereo and `0.90` recall are not simultaneously met by the current
  model, the YOLO26 student variants, or the YOLOv8n-P2 transfer baseline.
- Shrinking architecture alone is not enough; it trades away recall.
- Pretrained transfer helps accuracy but increases CPU cost.
- Exhaustive tile is too expensive.
- Sparse ROI tile/tracking plus better real far-ball training data is the next
  engineering path.
