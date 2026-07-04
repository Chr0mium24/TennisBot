# YOLO Search-S1b Hard-Negative Plan - 2026-07-04

## Purpose

Search-S1 improved the curated validation split but failed to improve the
held-out continuous replay. The next conservative experiment is Search-S1b:
keep the same YOLO26n-like P3/P4/P5 architecture and add confirmed empty
full-frame hard negatives.

This is still an offline detector experiment. It does not validate ROS/Gazebo,
stereo triangulation, target prediction, or chassis control.

## Data Decision

Keep `20260701_155008_cam1` and `20260701_155008_cam2` out of training. They
remain the final continuous replay set.

Available labeled image data:

| prefix | role | note |
|---|---|---|
| `20260701_154019_cam1` | val plus extra negatives | S1 val used 104 labeled frames; 125 remaining labeled frames are all empty |
| `20260701_154205_cam1` | train | 12 empty frames |
| `20260701_154812_cam1` | train | 9 empty frames |
| `20260701_155239_cam1` | train | 48 positive frames, 6 empty frames |
| `indoor_ball_sample*_cam1` | train | indoor positives and empties |
| `20260701_155008_cam1/cam2` | final replay only | excluded from train/val |

There are old `session_20260527_*_cam2` label files under the repo, but the
matching cam2 images are not present in the current workspace. They are not used.

Unlabeled 0260701 cam2 sequences are also not used as negative training data,
because an unlabeled image may still contain a ball. Treating those frames as
background would create false-negative labels.

## Dataset

Dataset root:

- `tools/yolo/workspace/runs/search_fullframe_s1b_hardneg_20260704`

Split:

| split | images | boxes | positive files | empty files |
|---|---:|---:|---:|---:|
| train | 332 | 157 | 157 | 175 |
| val | 104 | 52 | 52 | 52 |

Delta from Search-S1:

- train images: `207 -> 332`
- train empty frames: `50 -> 175`
- train positive boxes: unchanged at `157`
- val split: unchanged for direct metric comparison

## Training Command

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

repo = Path('/home/cr/Codes/TennisBot')
model = YOLO(str(repo / 'artifacts/models/tennis_ball_yolo/model.pt'))
model.train(
    data=str(repo / 'tools/yolo/workspace/runs/search_fullframe_s1b_hardneg_20260704/data.yaml'),
    epochs=60,
    imgsz=512,
    batch=16,
    device='0',
    workers=8,
    patience=12,
    project=str(repo / 'tools/yolo/workspace/runs/training'),
    name='search_s1b_yolo26n_fullframe_hardneg_imgsz512_20260704',
    seed=20260704,
    exist_ok=True,
)
PY
```

## Evaluation

Evaluate in three steps:

1. Compare S1b against S1 on the unchanged val split.
2. Replay `20260701_155008_cam1/cam2` with S1b as both search and ROI model.
3. Replay the intended two-model runtime:
   - search model: S1b
   - ROI model: `roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`

Promotion still requires continuous replay improvement, not training mAP alone.

