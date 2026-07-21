# YOLO Search-S1 Training Result - 2026-07-04

## Goal

Train the first full-frame search model from the current packaged YOLO26n-like
model, then verify it on the held-out continuous sequence before promoting it
for runtime use.

This is an offline detector/tracker replay result. It does not validate the
real ROS/chassis catch loop, stereo triangulation, target prediction, or chassis
control.

## Dataset

Dataset root:

- `tools/yolo/workspace/runs/search_fullframe_s1_20260704`

Held-out replay sequence:

- `20260701_155008_cam1`
- `20260701_155008_cam2`

Training/validation split:

| split | images | boxes | empty images | sequences |
|---|---:|---:|---:|---|
| train | 207 | 157 | 50 | `20260701_154205_cam1`, `20260701_154812_cam1`, `20260701_155239_cam1`, `indoor_ball_sample02_cam1`, `indoor_ball_sample_cam1` |
| val | 104 | 52 | 52 | `20260701_154019_cam1` |

## Training

Initial model:

- `artifacts/models/tennis_ball_yolo/model.pt`

Output:

- `tools/yolo/workspace/runs/training/search_s1_yolo26n_fullframe_imgsz512_20260704/weights/best.pt`

Command profile:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

repo = Path('/home/cr/Codes/TennisBot')
project = repo / 'tools/yolo/workspace/runs/training'
model = YOLO(str(repo / 'artifacts/models/tennis_ball_yolo/model.pt'))
model.train(
    data=str(repo / 'tools/yolo/workspace/runs/search_fullframe_s1_20260704/data.yaml'),
    epochs=60,
    imgsz=512,
    batch=16,
    device='0',
    workers=8,
    patience=12,
    project=str(project),
    name='search_s1_yolo26n_fullframe_imgsz512_20260704',
    seed=20260704,
    exist_ok=True,
)
PY
```

Training stopped early at epoch 24. Best mAP50-95 was at epoch 12.

| metric | best epoch | best value |
|---|---:|---:|
| precision(B) | 15 | 0.74808 |
| recall(B) | 24 | 0.49387 |
| mAP50(B) | 15 | 0.39755 |
| mAP50-95(B) | 12 | 0.17321 |

## Same-Data Validation Baseline

Both models were validated on the same `search_fullframe_s1_20260704` val split
at `imgsz=512` on CPU.

| model | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| packaged base model | 0.388 | 0.404 | 0.216 | 0.087 |
| Search-S1 best | 0.543 | 0.423 | 0.356 | 0.176 |

Search-S1 improved the held-out validation split, but this split did not predict
continuous replay quality on `20260701_155008`.

## Continuous Replay Results

Replay settings:

- Search imgsz: `512`
- ROI imgsz: `320`
- ROI window: `960x540`
- Expanded ROI: `1280x720`
- Held-out replay windows:
  - cam1: first 124 frames, 49 labeled balls
  - cam2: first 134 frames, 44 labeled balls
- Device: CPU, 10 torch threads

Generated detailed reports:

- `docs/current/yolo_base_stateful_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_base_stateful_sequence_155008_cam2_labeled_window_20260704.md`
- `docs/current/yolo_search_s1_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_search_s1_sequence_155008_cam2_labeled_window_20260704.md`
- `docs/current/yolo_search_s1_roi_crop_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_search_s1_roi_crop_sequence_155008_cam2_labeled_window_20260704.md`

| runtime config | cam | recall | precision | median ms/img | est per-cam stereo FPS |
|---|---|---:|---:|---:|---:|
| base model for search+ROI | cam1 | 0.469 | 0.284 | 22.32 | 22.41 |
| base model for search+ROI | cam2 | 0.432 | 0.463 | 18.36 | 27.23 |
| Search-S1 for search+ROI | cam1 | 0.408 | 0.465 | 26.38 | 18.95 |
| Search-S1 for search+ROI | cam2 | 0.500 | 0.293 | 12.11 | 41.29 |
| Search-S1 search + ROI crop model | cam1 | 0.449 | 0.629 | 19.27 | 25.95 |
| Search-S1 search + ROI crop model | cam2 | 0.273 | 0.203 | 12.56 | 39.80 |

Estimated actual stereo budget using the measured cam1+cam2 medians:

| runtime config | cam1+cam2 median ms | estimated stereo FPS |
|---|---:|---:|
| base model for search+ROI | 40.68 | 24.58 |
| Search-S1 for search+ROI | 38.49 | 25.98 |
| Search-S1 search + ROI crop model | 31.83 | 31.42 |

## Code Change

`tennisbot-yolo benchmark roi-track` now accepts:

```bash
--roi-model PATH
```

When this is supplied, unlocked/search frames use `--model`, while locked ROI
frames use `--roi-model`. This allows direct replay of the intended two-model
runtime architecture.

## Decision

Do not promote Search-S1.

Reasons:

- It improves the curated validation split, but not the held-out continuous
  replay that matters for runtime acquisition.
- The two-model runtime is fast enough in this offline replay, at about
  `31.42 FPS` estimated stereo, but recall is too low, especially cam2
  (`0.273`).
- The current validation split is too small and too weak; it misses the false
  locks and motion patterns in `20260701_155008`.

## Next Step

Build Search-S1b before another long training run:

1. Add hard negatives from replay false positives and false locks.
2. Add more sequence-level validation, including a continuous cam2 validation
   sequence, while keeping `20260701_155008` held out for final replay.
3. Re-train from the packaged base model with the same P3/P4/P5 architecture.
4. Promote only if continuous replay improves recall and the two-model replay
   remains above the runtime FPS target.

