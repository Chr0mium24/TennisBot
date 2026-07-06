# Small YOLO P2 Student Plan - 2026-07-06

## Goal

Train a small YOLO search student that is not just a lower-`imgsz` baseline.

The model should preserve small-target features with a P2/stride-4 head while reducing unnecessary large-object compute.

## Design

- Architecture: `tools/yolo/configs/tennis_yolo26_micro_p2_no_p5.yaml`
- Heads: P2/P3/P4 only
- Removed: P5 detect branch
- Width scale: `0.125`
- Input: `640`
- Task: coarse full-frame search for tennis ball acquisition

## Rationale

Lowering `imgsz` is not a real small-object solution. It cuts compute by shrinking the image, but it can erase the tennis ball before the model sees it.

For a search model, the output does not need final sub-pixel localization. It does need to preserve enough spatial evidence to say where to crop the next ROI. A P2 head keeps a high-resolution feature map for small objects, while removing P5 avoids spending detection capacity on large objects that do not exist in this task.

## Training Command

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

## Evaluation

After training, evaluate the resulting `weights/best.pt` on the same held-out `20260701_155008` frame list used for the small heatmap comparison:

```bash
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

Ultralytics resolved the relative `project` path under `runs/detect/...` in this run, so the actual checkpoint path is:

`runs/detect/tools/yolo/workspace/runs/training/small_yolo26_micro_p2_no_p5_aug1000_imgsz640_20260706/weights/best.pt`

## Success Bar

The small YOLO student has to beat the current full-frame YOLO `640` baseline:

- recall: `0.398`
- precision: `0.068`
- median latency: `5.17ms/img`

It should also be compared against the small heatmap student:

- recall: `0.720`
- precision: `0.293`
- median latency: `4.74ms/img`
