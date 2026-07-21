# YOLO Search Model Research Decision - 2026-07-04

## Purpose

Stop blind search-model experiments and choose the next model from evidence:
papers, open-source implementations, and the TennisBot runtime/data constraints.

This document is an offline vision-model plan. It does not validate the
real ROS/chassis catch loop, stereo triangulation, target prediction, or chassis
control.

## Sources Reviewed

Sports-ball tracking:

- TrackNet paper page:
  <https://huggingface.co/papers/1907.03698>
- TrackNet PyTorch implementation:
  <https://github.com/yastrebksv/TrackNet>
- WASB paper:
  <https://papers.bmvc2023.org/0310.pdf>
- WASB repository:
  <https://github.com/nttcom/WASB-SBDT>
- BlurBall repository:
  <https://github.com/cogsys-tuebingen/blurball>

Small-object detection and deployment:

- Ultralytics YOLOv8-P2 YAML:
  <https://github.com/ultralytics/ultralytics/blob/main/ultralytics/cfg/models/v8/yolov8-p2.yaml>
- SAHI repository:
  <https://github.com/obss/sahi>
- GSConv/Slim-Neck paper:
  <https://arxiv.org/pdf/2206.02424>
- Ultralytics YOLO26 docs:
  <https://docs.ultralytics.com/models/yolo26>
- Ultralytics model YAML guide:
  <https://docs.ultralytics.com/guides/model-yaml-config>

## Research Readout

### 1. Sports ball tracking is usually a heatmap/point task

TrackNet and WASB do not treat the ball as a normal large object. They predict
high-resolution heatmaps or point locations and use consecutive frames or
temporal consistency. This matches our failure mode: the ball is small, fast,
sometimes blurred, and may be visually weak in one frame.

WASB is especially relevant: its key ingredients are high-resolution feature
extraction, position-aware training, and temporal consistency. BlurBall extends
this family by explicitly modeling motion blur for table-tennis balls.

Implication for TennisBot:

- The final best tracker is likely not a plain single-frame box detector.
- A heatmap/temporal model is plausible for the search/acquisition role.
- But it requires point/heatmap training data and careful sequence labels. Our
  current local data is sparse YOLO boxes, so implementing WASB/TrackNet now
  would be a larger data-format project, not just a model YAML swap.

### 2. P2/stride-4 detection is the right YOLO teacher direction

The official YOLOv8-P2 architecture adds a P2/4 detection output alongside
P3/P4/P5. That is the correct YOLO-style response to tiny objects because a
stride-8 first head is too coarse when the ball is only a few resized pixels.

Implication for TennisBot:

- P2 is useful as a high-recall teacher or pseudo-labeler.
- P2 is not automatically a runtime model because it is slower on CPU.
- Our previous local sweep supports this: `tennis_yolov8n_p2.yaml` had the best
  validation/sample recall among trained P2 candidates, but was too slow for
  the CPU stereo runtime budget.

### 3. Slicing/SAHI solves pixels but not frame budget

SAHI-style sliced inference is built to detect small objects in large images.
This is conceptually correct for 4K tennis-ball search, but exhaustive slicing
is too expensive every frame. Our local tile probes already showed exhaustive
tile inference misses the FPS target.

Implication for TennisBot:

- Do not use full-frame exhaustive SAHI/tiling every frame.
- Use sparse ROI, recovery search, and offline teacher labeling instead.
- Sliced teacher inference can be useful to mine pseudo labels from unlabeled
  full-frame sequences.

### 4. GSConv/Slim-Neck is not the next bottleneck

GSConv/Slim-Neck targets lightweight detector neck efficiency. That may help
later, but our current failures are recall/data/assignment failures. The local
Ghost/P2 latency screen was also not favorable.

Implication for TennisBot:

- Do not start by adding GSConv modules.
- First build a strong teacher and better labels.
- Consider GSConv only after the teacher has enough recall and the student
  distillation target is clear.

### 5. YOLO26 is good for runtime, not necessarily for first teacher

YOLO26 has deployment-friendly properties: DFL-free regression, end-to-end
inference, and a lighter head. The current packaged runtime model is already
YOLO26n-like and runs well in ROI. But local YOLO26 P2 students trained from
scratch were recall-starved.

Implication for TennisBot:

- Keep YOLO26n/ROI model as the runtime-biased path.
- Use a pretrained P2 teacher first, then distill or pseudo-label a faster
  runtime search model.

## Local Constraints

Current held-out sequence:

- `20260701_155008_cam1`
- `20260701_155008_cam2`

Do not train on those; keep them for replay.

Available data issue:

- Most non-held-out positives are cam1.
- Non-held-out cam2 positive images are not available in the current workspace.
- Hard negatives improved precision but lowered recall in Search-S1b.

Runtime issue:

- Full-frame search must not run every frame after lock.
- Runtime target still requires stateful ROI and sparse recovery.
- P2 teacher speed can be slow because it is not promoted directly to runtime.

## Decision

Build and train `Search-S2 Teacher`:

| Field | Choice |
|---|---|
| Role | offline high-recall teacher and pseudo-labeler |
| Architecture | `tools/yolo/configs/tennis_yolov8n_p2.yaml` |
| Init | `yolov8n.pt` partial pretrained transfer |
| Heads | P2/P3/P4/P5 |
| Train data | `search_fullframe_s1b_hardneg_20260704` |
| Train imgsz | `640` |
| Runtime promotion | no, teacher only |
| Evaluation | held-out `20260701_155008` replay |

Why this model:

- It is the strongest already-screened local architecture by recall.
- It follows official Ultralytics P2 design.
- It avoids custom modules and custom losses.
- It can be trained immediately and used to mine positive pseudo labels.

What would change promotion:

- If Search-S2 teacher still fails on `155008`, the next step is data, not more
  YOLO neck edits: recover cam2 positives, add point/blur labels, or implement a
  WASB/TrackNet-style heatmap pipeline.

## Post-Training Update

Search-S2 was trained and tested. It did not meet the teacher requirement:

- best validation recall: `0.07692`;
- best validation mAP50: `0.07903`;
- held-out `155008` replay recall: `0.184` on cam1 and `0.205` on cam2;
- estimated CPU stereo FPS with S2 search remained around `11-14` because the
  tracker stayed in full-frame search for most frames.

Detailed result:

- `docs/current/yolo_search_s2_teacher_result_20260704.md`

Decision after training: do not promote S2 and do not keep changing YOLO necks
blindly. The next useful build is a temporal heatmap/point teacher, because the
research-backed TrackNet/WASB family is built around consecutive frames and
high-resolution localization for very small, fast sports balls.
