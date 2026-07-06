# Small YOLO P2 Student Compare Result - 2026-07-06

## Scope

This records a newly trained small YOLO search student and compares it against the small heatmap student.

This is an offline detector/search comparison only. It does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## User Question

The concern was correct: a small-object search model should not simply lower `imgsz`.

The tested YOLO student therefore kept `imgsz=640` and changed the architecture instead:

- P2/stride-4 detection head for tiny objects;
- P3/P4 retained;
- P5 removed;
- very small width scale.

## Training

Architecture:

`tools/yolo/configs/tennis_yolo26_micro_p2_no_p5.yaml`

Actual checkpoint:

`runs/detect/tools/yolo/workspace/runs/training/small_yolo26_micro_p2_no_p5_aug1000_imgsz640_20260706/weights/best.pt`

Training command:

```bash
uv run --project tools/yolo --extra detect yolo detect train \
  model=tools/yolo/configs/tennis_yolo26_micro_p2_no_p5.yaml \
  data=tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/data.yaml \
  epochs=30 \
  patience=8 \
  batch=32 \
  imgsz=640 \
  device=0 \
  workers=8 \
  project=tools/yolo/workspace/runs/training \
  name=small_yolo26_micro_p2_no_p5_aug1000_imgsz640_20260706 \
  exist_ok=True \
  seed=20260706 \
  plots=False
```

Training finished in `0.101` hours.

Model size after fusion:

| model | params | GFLOPs | checkpoint |
|---|---:|---:|---:|
| small YOLO26 micro P2 no-P5 | 279,491 | 1.6 | 1.1 MB |

Training validation reported:

| split | images | instances | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|---:|
| train-run val | 163 | 118 | 0.902 | 0.449 | 0.522 | 0.420 |

## Held-Out 155008 Evaluation

Command:

```bash
find tools/yolo/workspace/dataset/images/0260701 -maxdepth 1 -type f \
  -name '20260701_155008_cam*_frame_*.jpg' | sort > /tmp/tennisbot_155008_samples.txt

uv run --project tools/yolo --extra detect tennisbot-yolo benchmark roi-sample \
  --model runs/detect/tools/yolo/workspace/runs/training/small_yolo26_micro_p2_no_p5_aug1000_imgsz640_20260706/weights/best.pt \
  --sample-list /tmp/tennisbot_155008_samples.txt \
  --sample-limit 0 \
  --full-imgsz-values 640 \
  --roi-profile roi_960x540_320:960:540:320 \
  --coarse-imgsz 640 \
  --device 0 \
  --threads 0 \
  --conf 0.05 \
  --iou 0.7 \
  --match-iou 0.5 \
  --max-detections 300 \
  --output-markdown docs/current/small_yolo_p2_student_result_20260706.md
```

Result on `20260701_155008`:

| model | mode | imgsz | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| small YOLO P2 no-P5 | full-frame | 640 | 20 | 65 | 73 | 0.215 | 0.235 | 5.05 | 99.07 |

## Comparison

| candidate | search input | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| old YOLO full-frame | 640 | 37 | 509 | 56 | 0.398 | 0.068 | 5.17 | 96.78 |
| small YOLO P2 no-P5 | 640 | 20 | 65 | 73 | 0.215 | 0.235 | 5.05 | 99.07 |
| small heatmap | 5xRGB 480x270 | 67 | 162 | 26 | 0.720 | 0.293 | 4.74 | 105.43 |

## Readout

The small YOLO P2/no-P5 model did what it was designed to do on compute: it is tiny and fast.

It did not solve search recall:

- it improved precision compared with old full-frame YOLO;
- it lost recall badly on the held-out continuous sequence;
- it did not beat the old YOLO `640` baseline, and it is far below the small heatmap student.

This suggests the failure is not only model size or P2 availability. The main issue is that single-frame full-image bbox detection remains brittle for a tiny, fast ball with limited real positive labels.

## Is The Objective Wrong?

The objective is not wrong if stated as:

`fast coarse acquisition -> crop ROI -> verify/refine -> stereo match`

The objective is wrong if stated as:

`full-frame tiny-object detector must directly find every ball precisely at low cost`

For runtime, the search model does not need exact bbox geometry. It needs enough coarse localization to put the ball inside the next ROI. That favors:

- point/heatmap output;
- temporal context or motion cues;
- ROI confirmation after search;
- high recall over final localization precision.

Small YOLO is still useful for ROI verification/refinement, but this experiment does not support small YOLO as the main full-frame search model.

## Next Step

Continue the heatmap-student branch, but address the user's `480x270` information-loss concern directly:

1. train `640x360` heatmap with the same labels and compare recall/FPS;
2. train `3`-frame heatmap to reduce buffering and compute;
3. evaluate heatmap search after ROI YOLO confirmation, not only raw heatmap FP;
4. do not promote full-frame small YOLO search unless it is trained with much stronger data or a sliced/tiled acquisition design.
