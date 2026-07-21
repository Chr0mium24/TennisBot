# YOLO Search Model Architecture - 2026-07-04

## Goal

Design the next model specifically for full-frame ball acquisition. This model
is separate from the locked ROI model.

Runtime role:

- `search model`: find coarse ball candidates when the tracker is unlocked or
  lost;
- `ROI model`: refine detections while locked in a small crop;
- stereo pairing and tracker gates reject false candidates before updating the
  real lock.

This is an architecture/training plan only. It does not claim real ROS/chassis or live
camera validation.

## Current Evidence

Continuous replay on `20260701_155008` showed:

- `search416/roi320` is fast but low recall.
- `search512/roi320` improves recall:
  - cam1: `0.367 -> 0.735`
  - cam2: `0.386 -> 0.500`
- Bigger ROI did not fix recall.
- Same-frame recovery helps only when the tracker is already in ROI mode.

Therefore the next bottleneck is full-frame acquisition, not ROI crop size.

## Primary Runtime Architecture: Search-S1

Use the current YOLO26n-like architecture as the first search model.

Architecture:

| Component | Design |
|---|---|
| Family | YOLO26n-style end-to-end detector |
| Init | `artifacts/models/tennis_ball_yolo/model.pt` |
| Detect strides | P3/P4/P5, strides `8,16,32` |
| P2 | not in S1 |
| Classes | one class: `tennis_ball` |
| Runtime imgsz | `512` |
| Training imgsz | start `512`, compare `640` |
| Output role | coarse candidates, not final target |
| Threshold | low `conf`, e.g. `0.02-0.05` |
| max_det | keep multiple candidates, e.g. `20-50` |

Why S1 first:

- It can transfer from the current model.
- It already runs near the measured quality-mode speed: about `29 FPS` estimated
  stereo in the continuous replay.
- Existing P2-from-scratch trials had poor recall.
- YOLOv8n-P2 was more accurate than tiny students but too slow for CPU runtime.

S1 should be trained for recall, not clean final precision. False positives are
acceptable if the stereo pairer and ROI confirmation reject them.

## P2 Architecture: Search-S2 Teacher

Use a P2 model only as a recall upper-bound or teacher, not the first runtime
candidate.

Candidate architectures:

| Candidate | Detect heads | Use |
|---|---|---|
| `tennis_yolov8n_p2.yaml` | P2/P3/P4/P5 | pretrained P2 teacher candidate |
| YOLO26n-P2 YAML | P2/P3/P4/P5 | architecture reference; no local P2 weights |
| YOLO26 P2 no-P5 | P2/P3/P4 | possible student after teacher exists |

Reason:

- Full-frame tiny balls can benefit from P2, but P2 is expensive on CPU.
- YOLO26 P2 has no ready P2 pretrained weights in the local path.
- Prior YOLO26 micro/tiny P2 no-P5 models trained from scratch were
  recall-starved.

S2 is useful if S1 cannot meet acquisition recall. It can produce pseudo labels
or soft targets for a smaller runtime student.

## Distilled Runtime Student: Search-S3

Only start S3 after S1/S2 expose a strong teacher.

Architecture target:

- YOLO26-derived P2/P3/P4 no-P5;
- width between previous tiny P2 and YOLO26n width;
- end-to-end head, `reg_max=1`;
- input `512`;
- trained with teacher pseudo labels and hard negatives.

Do not train another tiny P2 model from scratch as the next step. That already
failed the recall target.

## Data Shape

Search data should match full-frame acquisition:

- real full-frame images with positive labels;
- empty full-frame negatives;
- hard negatives from false locks in continuous replay;
- optional large-context crops, not only `960x540` ROI crops;
- avoid training only on small ROI crops, because that does not teach full-frame
  acquisition.

Recommended split:

- include continuous captures such as `20260701_154019` and `20260701_155008`;
- keep sequence-level validation so adjacent frames do not leak into train/val;
- keep a dedicated continuous replay set for final search evaluation.

## Training Plan

S1 command profile:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

model = YOLO("artifacts/models/tennis_ball_yolo/model.pt")
model.train(
    data="tools/yolo/workspace/runs/search_fullframe_20260704/data.yaml",
    epochs=60,
    imgsz=512,
    batch=16,
    device="0",
    workers=8,
    patience=12,
    project="tools/yolo/workspace/runs/training",
    name="search_s1_yolo26n_fullframe_imgsz512_20260704",
    seed=20260704,
    exist_ok=True,
)
PY
```

Then evaluate:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo benchmark roi-track \
  --model tools/yolo/workspace/runs/training/search_s1_yolo26n_fullframe_imgsz512_20260704/weights/best.pt \
  --sequence-glob 'tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam1_frame_*.jpg' \
  --sample-limit 124 \
  --device cpu --threads 10 \
  --search-imgsz 512 --roi-imgsz 320 \
  --roi-width 960 --roi-height 540 \
  --expanded-width 1280 --expanded-height 720
```

For the final two-model replay, use S1 only for search and the ROI crop model
for locked ROI. The current benchmark uses one model for both, so it needs a
two-model option before final promotion.

## Promotion Criteria

Do not promote based on training mAP alone. Promote only if continuous replay
improves:

| Metric | Minimum target |
|---|---:|
| cam1 search/track recall | `>= 0.80` |
| cam2 search/track recall | `>= 0.65` |
| precision after tracker/stereo filters | no worse than current quality mode |
| estimated stereo FPS in quality profile | `>= 28` |
| locked ROI FPS | remains near `40-50` when search is not active |

The long-term target is still higher recall, but these thresholds would show
that training improved the current acquisition bottleneck.

## Decision

Train Search-S1 first:

- YOLO26n-like P3/P4/P5;
- initialized from the current package;
- full-frame/high-context search data;
- runtime imgsz `512`;
- high recall, multiple candidates.

Do not make P2 the first runtime architecture. Use P2 as a teacher/distillation
path only if Search-S1 cannot raise recall enough.
