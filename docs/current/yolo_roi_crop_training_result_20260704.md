# YOLO ROI Crop Training Result - 2026-07-04

## Scope

This document records the first ROI/crop fine-tuning trial after the stateful
ROI replay logic was added.

This is still an offline detector/runtime proof:

- no real ROS/chassis catch-loop validation;
- no live USB camera capture in this run;
- no stereo triangulation timing in the benchmark;
- no chassis control or `/target/raw` closed-loop claim.

The purpose is to answer whether the ROI-first detector plan can run fast enough
before spending more time on model training.

## Logic Status

Implemented and committed before this training run:

- `tools/yolo/src/tennisbot_yolo/roi_tracking.py`
- `tennisbot-yolo benchmark roi-track`

State behavior:

- full-frame `SEARCH` when unlocked;
- `LOCKED` ROI crop around the previous detection;
- pixel-velocity prediction for the next ROI center;
- expanded ROI after a miss or near-edge detection;
- fallback to full-frame `SEARCH` after configured misses.

This logic is currently proven through offline replay. It is not yet wired into
the ROS `tennisbot_vision_runtime` detector path.

## Dataset

Generated a ROI crop dataset under:

`tools/yolo/workspace/runs/roi_crop_960x540_imgsz320_20260704`

Generation settings:

- crop size: `960x540`
- target imgsz: `320`
- margin: `24 px`
- source: real labeled frames
- positive crop anchors: 5x5 ratio grid around each labeled ball
- max positive crops per source box: `8`
- negative crop target ratio: `0.5`
- negative crop rejection: IoU greater than `0.01` with any label

Generated counts:

| item | count |
|---|---:|
| labeled source images scanned | 693 |
| positive crops | 2337 |
| negative crops | 1168 |
| train images | 2804 |
| val images | 701 |

## Training

Base model:

`artifacts/models/tennis_ball_yolo/model.pt`

Command profile:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

project = Path('/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/training')
model = YOLO('/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo/model.pt')
model.train(
    data='/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/roi_crop_960x540_imgsz320_20260704/data.yaml',
    epochs=30,
    imgsz=320,
    batch=64,
    device='0',
    workers=8,
    patience=8,
    project=str(project),
    name='roi_crop_960x540_teacher_imgsz320_20260704',
    seed=20260704,
    exist_ok=True,
)
PY
```

Best weight:

`tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`

Validation summary from `results.csv`:

| metric | best | epoch |
|---|---:|---:|
| precision | 0.937610 | 27 |
| recall | 0.921840 | 25 |
| mAP50 | 0.929180 | 29 |
| mAP50-95 | 0.729730 | 30 |

Final validation line:

| precision | recall | mAP50 | mAP50-95 |
|---:|---:|---:|---:|
| 0.924610 | 0.910470 | 0.929020 | 0.729730 |

## CPU Runtime Proof

Generated raw reports:

- `docs/current/yolo_roi_crop_sample_20260704.md`
- `docs/current/yolo_roi_crop_stateful_replay_20260704.md`

The stateful raw report stores the `search512/roi320` run. The `search320` and
`search416` rows below were additional console probes with the same ROI settings.

### ROI-only upper bound

Command:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo benchmark roi-sample \
  --model tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt \
  --device cpu --threads 10 --sample-limit 60 --real-only \
  --full-imgsz-values 320,416,512 \
  --roi-profile roi_768x432_320:768:432:320 \
  --roi-profile roi_960x540_320:960:540:320 \
  --coarse-imgsz 416 \
  --output-markdown docs/current/yolo_roi_crop_sample_20260704.md
```

Key rows:

| mode | profile | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|
| full | full_320 | 0.571 | 0.640 | 10.18 | 49.13 |
| full | full_416 | 0.607 | 0.531 | 14.92 | 33.52 |
| full | full_512 | 0.643 | 0.692 | 18.24 | 27.42 |
| oracle_roi | 768x432@320 | 0.964 | 0.540 | 10.32 | 48.44 |
| oracle_roi | 960x540@320 | 1.000 | 0.500 | 10.33 | 48.43 |
| coarse_roi | 416+960x540@320 | 0.821 | 0.548 | 25.68 | 19.47 |

Readout:

- Locked small ROI can hit the requested `40-50 FPS` stereo detector budget.
- Same-frame full search plus ROI is only about `19.5 FPS`, so it is not the
  target runtime path.
- Full-frame low-imgsz is fast, but recall is still too low for final ball
  observations.

### Stateful replay

Sequence:

`tools/yolo/workspace/dataset/images/0260701/20260701_154019_cam1_frame_*.jpg`

The measured sequence has `452` images and `52` GT ball boxes.

Key rows after ROI crop training:

| search imgsz | ROI imgsz | search frames | ROI frames | expanded ROI | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 320 | 320 | 368 | 84 | 31 | 19 | 45 | 33 | 0.365 | 0.297 | 16.54 | 30.24 |
| 416 | 320 | 363 | 89 | 13 | 37 | 61 | 15 | 0.712 | 0.378 | 13.17 | 37.98 |
| 512 | 320 | 352 | 100 | 21 | 37 | 65 | 15 | 0.712 | 0.363 | 16.15 | 30.96 |

The best current tradeoff is `search416/roi320`:

- recall improved to `0.712` on the ordered replay;
- estimated stereo FPS is `37.98`;
- it still does not hold ROI lock long enough to sustain `40-50 FPS`.

## Decision

The ROI/crop model is worth continuing. It directly fixes the small-object
compression problem because the crop happens before YOLO resize.

The full-frame acquisition path should be treated separately from the locked ROI
path:

- locked ROI model: optimize for small-ball recall and stable localization;
- full-frame search model: optional later, optimize for coarse high-recall
  acquisition only;
- full-frame low-imgsz training cannot recover detail already destroyed by
  resizing a 4K frame to `320` or `416`.

Do not use same-frame full search plus ROI as the normal runtime. It proves the
crop chain works, but its cost is closer to `15-20 FPS` stereo.

## Next Steps

1. Wire stateful ROI into the real `YoloBallDetector.detect_pair` path behind
   explicit runtime parameters.
2. Replay or live-test left/right detection together, because stereo pairing may
   reject some monocular false positives.
3. Package the ROI crop `best.pt` only after deciding whether the runtime uses
   one model or a split search/ROI model.
4. If acquisition remains the bottleneck, train a separate full-frame search
   model for coarse candidate recall, not for final small-ball localization.
