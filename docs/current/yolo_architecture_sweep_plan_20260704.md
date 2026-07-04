# YOLO Architecture Sweep Plan - 2026-07-04

## Purpose

Broaden the model search beyond one custom YOLO26 micro-P2 config. The goal is
to find a CPU-oriented detector that can keep far tennis-ball recall high without
throwing away 4K source fidelity.

Hard target:

- CPU stereo detector throughput near `30 FPS`.
- Recall target `0.90`.
- No quantization in this phase.

## Candidate Families

### Low-risk local candidates

These use modules already present in the current Ultralytics environment.

| Config | Family | Change | Transfer path | Why test |
|---|---|---|---|---|
| `tennis_yolo26_micro_p2.yaml` | YOLO26 | P2/P3/P4/P5, width 0.125 | none/current experiment | Fast lower bound |
| `tennis_yolo26_micro_p2_no_p5.yaml` | YOLO26 | remove P5 from micro-P2 | load micro-P2 best if compatible | Small-target-only head ablation |
| `tennis_yolo26_tiny_p2_no_p5.yaml` | YOLO26 | width 0.1875, remove P5 | mostly scratch | Recover capacity without full nano cost |
| `tennis_yolov8n_p2.yaml` | YOLOv8 | official-style P2 | partial `yolov8n.pt` transfer | Non-YOLO26 P2 baseline with pretrained backbone |
| `tennis_yolov8n_ghost_p2.yaml` | YOLOv8-Ghost | GhostConv/C3Ghost P2 | weak partial transfer | Lightweight module comparison |

### External/GitHub candidates to watch

These are not first-pass integrations because they require custom source modules
or losses. They should enter only after a local YAML-only sweep proves the data
pipeline and target metric are stable.

| Candidate | Source | Claimed idea | Integration risk |
|---|---|---|---|
| FDM-YOLO | <https://github.com/zdw0513-source/FDM-YOLO> | high-resolution/multi-scale fusion, attention, small-target UAV focus | dual-modality/fusion assumptions and custom code |
| YOLOv8-C2f-Faster-EMA / Improved_YOLOv8s | <https://github.com/Username378/Improved_YOLOv8s> | Slim-neck, C2f-Faster, EMA, DyHead options | forked Ultralytics code, old dependencies |
| YOLO-TLP | <https://github.com/irfan112/YOLO-TLP> | tiny-object focus for targets under about 15 px | unclear fit with current training/export chain |
| DroneScan-YOLO | <https://github.com/yannbellec/dronescan-yolo> | P2 branch plus tiny-object loss changes and pruning | new loss/pruning logic, paper newer than local stack |

## Screening Protocol

1. Confirm every YAML loads and records parameter count/stride.
2. Run a quick CPU latency probe at `imgsz=416/512/640`.
3. Train promising configs on the current 1000-image trial split.
   - Initial screening may use fewer epochs.
   - Any candidate that looks close must be rerun for `30` epochs.
4. Evaluate all trained candidates on the same 60-image CPU sample used by the
   previous edge fidelity probe.
5. Save results in Markdown before promotion.

## Executed Sweep

YAML/load screen:

| Model/config | Params | Strides | Median ms @416 | Median ms @512 | Median ms @640 | Decision |
|---|---:|---|---:|---:|---:|---|
| `yolo26n.yaml` | 2,572,280 | 8,16,32 | 21.70 | 26.54 | 35.24 | Reference only |
| `yolo26n-p2.yaml` | 2,662,400 | 4,8,16,32 | 32.39 | 47.59 | 73.36 | Deferred, no P2 weights |
| `tennis_yolo26_micro_p2.yaml` | 406,680 | 4,8,16,32 | 16.93 | 25.12 | 39.29 | Trained 30 epochs |
| `tennis_yolo26_micro_p2_no_p5.yaml` | 310,094 | 4,8,16 | 15.39 | 22.38 | 34.79 | Trained 30 epochs |
| `tennis_yolo26_tiny_p2_no_p5.yaml` | 649,466 | 4,8,16 | 21.29 | 28.63 | 43.66 | Trained 30 epochs |
| `tennis_yolov8n_p2.yaml` | 2,926,692 | 4,8,16,32 | 35.30 | 49.34 | 71.49 | Trained 30 epochs with batch 8 |
| `tennis_yolov8n_ghost_p2.yaml` | 1,606,492 | 4,8,16,32 | 44.08 | 66.83 | 94.02 | Deferred, slower than plain YOLOv8n-P2 |
| `yolo11n.yaml` | 2,583,160 | 8,16,32 | 26.45 | 36.36 | 51.49 | Reference only |

Training result summary:

| Run | Init | Batch | Best recall | Best mAP50 | Best mAP50-95 | Result |
|---|---|---:|---:|---:|---:|---|
| `tennis_yolo26_micro_p2_aug1000_batch32_imgsz640_20260704` | YAML/scratch | 32 | 0.50000 | 0.53251 | 0.40663 | Too little recall |
| `tennis_yolo26_micro_p2_no_p5_aug1000_batch32_imgsz640_20260704` | compatible transfer | 32 | 0.55085 | 0.57782 | 0.43830 | Best YOLO26 student, still too low |
| `tennis_yolo26_tiny_p2_no_p5_aug1000_batch32_imgsz640_20260704` | mostly scratch | 32 | 0.51451 | 0.53500 | 0.42264 | More capacity did not solve recall |
| `tennis_yolov8n_p2_aug1000_batch8_imgsz640_20260704` | partial `yolov8n.pt` transfer | 8 | 0.65329 | 0.68570 | 0.53769 | Best accuracy, too slow |

CPU sample result:

| Model | Best sample row | Readout |
|---|---|---|
| current package | `imgsz=640`, recall 0.786, precision 0.324, 12.90 est stereo FPS | Best recall among compared sample rows, misses speed |
| YOLO26 micro-P2 | `imgsz=512/640`, recall 0.571, 16.35/15.07 est stereo FPS | Smaller but recall collapses |
| YOLO26 micro-P2 no-P5 | `imgsz=640`, recall 0.595, 14.50 est stereo FPS | Best student sample recall, still far below target |
| YOLO26 tiny-P2 no-P5 | `imgsz=512`, recall 0.571, precision 0.615, 14.23 est stereo FPS | Extra width helped precision more than recall |
| YOLOv8n-P2 | `imgsz=512`, recall 0.643, precision 0.730, 12.53 est stereo FPS | Stronger accuracy, slower CPU path |

Full table is saved in
`docs/current/yolo26_cpu_architecture_research_20260704.md`.

## Promotion Rule

A model is not promoted by parameter count alone. It must beat the current
package on the recall/FPS tradeoff. A fast model with recall near `0.55` is a
negative result, even if it hits a synthetic latency target.

The runtime path should remain sparse ROI/tile-first unless a model alone
actually reaches both recall and FPS targets.

## Decision

No candidate is promoted as the runtime detector.

The next useful experiment is not another tiny YAML from scratch. It is a data
and crop experiment:

1. Build runtime-shaped positive crop data from real 4K labels.
2. Fine-tune the current YOLO26n-like package/teacher on those crops.
3. Validate full-frame fallback plus sparse ROI behavior.
4. Distill to a small YOLO26 student only after teacher recall is near the target.
