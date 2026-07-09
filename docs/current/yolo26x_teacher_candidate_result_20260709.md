# YOLO26x Teacher Candidate Result - 2026-07-09

## Summary

`yolo26x.pt` can be fine-tuned into a useful offline candidate generator, but it
does not solve the tiny fixed-exposure ball problem by capacity alone.

On the frozen 112-image small-ball benchmark, the trained `yolo26x` teacher at
`imgsz=1536` reached:

| metric | result |
|---|---:|
| IoU50 recall at `conf=0.05` | `29/112 = 0.259` |
| center-16 recall at `conf=0.001` | `55/112 = 0.491` |
| center-16 recall at `conf=0.05` | `48/112 = 0.429` |

This is slightly better than the current P2 no-P5 small model on the same small
benchmark (`26/112` IoU50 at `conf=0.05`, `49/112` center-16 at `conf=0.001`),
but the margin is small and false positives are high at low confidence.

## Answer: Should The Teacher Add P2?

For pseudo/candidate labeling, the teacher and student do not need the same
architecture. The teacher only has to output boxes for review. A larger and
slower teacher is acceptable.

For this dataset, however, P2 is still likely useful for a strong teacher:

- `yolo26x.pt` uses the normal P3/P4/P5 detection strides, so its smallest
  detection stride is `8`.
- The hard balls are often around `4-8 px`, so they sit at the edge of what a
  stride-8 head can localize.
- The large P3/P4/P5 teacher did improve small-ball recall slightly, but not
  enough to call it reliable.

Recommended next teacher, if we continue this route: a larger custom P2 model
or a P2/P3/P4/P5 teacher. The runtime student can still be smaller and may use a
different architecture.

## Raw COCO Smoke Test

Before fine-tuning, raw COCO `yolo26x.pt` was tested as class `sports ball`
candidate generator on the frozen 112-image small benchmark:

| item | value |
|---|---:|
| images | `112` |
| images with any candidate | `6` |
| total candidates | `8` |
| IoU50 hits | `0` |
| IoU30 hits | `0` |
| center-16 hits | `0` |
| center-32 hits | `0` |

Conclusion: pretrained COCO `yolo26x.pt` cannot directly label these tennis
balls. Fine-tuning is required.

Remote output:

`tools/yolo/workspace/runs/teacher_candidates/yolo26x_coco_sportsball_benchmark_smoke_20260709`

## Teacher Training

Remote host:

`anilam@10.31.151.120`

Model:

`yolo26x.pt`

Training data:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml`

Training command:

```bash
/home/anilam/Downloads/vision/yolo_training/.venv/bin/yolo detect train \
  model=yolo26x.pt \
  data=tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml \
  epochs=12 patience=4 imgsz=960 batch=4 device=0 workers=4 \
  project=tools/yolo/workspace/runs/training \
  name=yolo26x_teacher_final_trainpool_imgsz960_batch4_20260709 \
  pretrained=True cache=False plots=True \
  hsv_h=0 hsv_s=0 hsv_v=0 degrees=0 translate=0 scale=0 shear=0 perspective=0 \
  flipud=0 fliplr=0 mosaic=0 mixup=0 copy_paste=0 cutmix=0 erasing=0 auto_augment=none
```

Training completed 12 epochs. The actual Ultralytics output directory was:

`runs/detect/tools/yolo/workspace/runs/training/yolo26x_teacher_final_trainpool_imgsz960_batch4_20260709`

Important training facts:

| item | value |
|---|---:|
| parameters | `58,810,878` |
| GFLOPs | `208.5` |
| transferred weights | `1080/1092` |
| train images | `12,549` |
| val images | `1,390` |
| best mAP50-95 epoch | `10` |
| best mAP50-95 | `0.49295` |
| final epoch mAP50-95 | `0.49210` |
| final epoch precision | `0.90534` |
| final epoch recall | `0.73524` |

Note: some validation `cls_loss` entries were `nan`, but detection metrics were
computed and training finished. Treat internal val metrics as secondary; the
frozen raw benchmark below is the main comparison.

## Frozen Raw Benchmark

Evaluation settings:

| item | value |
|---|---|
| model | `best.pt` |
| manifest | `tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/manifest_remote_eval.jsonl` |
| split | `benchmark` |
| images | `381` |
| imgsz | `1536` |
| prediction conf | `0.001` |
| report thresholds | `0.001, 0.05, 0.25` |
| device | `0` |

Remote reports:

- `tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/yolo26x_teacher_best_small_eval_imgsz1536_20260709.md`
- `tools/yolo/workspace/runs/final_raw_benchmark_v1_20260708/yolo26x_teacher_best_all_eval_imgsz1536_20260709.md`
- `tools/yolo/workspace/runs/teacher_candidates/yolo26x_teacher_best_imgsz1536_20260709/benchmark_center_metrics.md`

Small-ball bucket:

| conf | images | gt | preds | IoU50 R | IoU30 R | center-16 R | center-32 R |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.001` | `112` | `112` | `1250` | `0.312` | `0.482` | `0.491` | `0.491` |
| `0.010` | `112` | `112` | `339` | `0.286` | `0.446` | `0.446` | `0.446` |
| `0.050` | `112` | `112` | `143` | `0.259` | `0.429` | `0.429` | `0.429` |
| `0.250` | `112` | `112` | `54` | `0.161` | `0.304` | `0.304` | `0.304` |

All benchmark buckets:

| conf | gt | TP IoU50 | FP | FN | IoU50 recall | precision | empty FP images |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.001` | `289` | `210` | `3347` | `79` | `0.727` | `0.059` | `91` |
| `0.050` | `289` | `204` | `342` | `85` | `0.706` | `0.374` | `75` |
| `0.250` | `289` | `189` | `114` | `100` | `0.654` | `0.624` | `46` |

Medium and large balls are mostly solved by this teacher. The hard failure mode
remains tiny fixed-exposure balls.

## Candidate Labels

Generated remote output:

`tools/yolo/workspace/runs/teacher_candidates/yolo26x_teacher_best_imgsz1536_20260709/train_pool_all`

Generated files:

| file or dir | purpose |
|---|---|
| `candidates_conf0001.csv` | all low-confidence candidate boxes with confidence and xyxy |
| `labels_conf0001/` | YOLO-format candidate labels at `conf>=0.001` |
| `labels_conf0050/` | YOLO-format candidate labels at `conf>=0.05` |
| `images.txt` | train-pool image list |
| `summary.json` | machine-readable summary |
| `summary.md` | readable summary |

Train-pool candidate counts:

| conf | predictions | images with candidates | empty images with candidates |
|---:|---:|---:|---:|
| `0.001` | `13,265` | `1,430/1,439` | `495/504` |
| `0.010` | `4,281` | `1,375/1,439` | `441/504` |
| `0.050` | `2,030` | `1,271/1,439` | `362/504` |
| `0.250` | `1,029` | `913/1,439` | `221/504` |

Both label directories contain `1,439` files. These are candidate labels only,
not approved training labels.

## Decision

Use this `yolo26x` teacher for candidate review on medium/large cases and as a
hard-negative mining source, but do not trust it as an automatic labeler for
tiny balls.

For tiny-ball recall, the next useful teacher experiment is P2-enabled. The
student does not have to share the same structure unless we are transferring
weights directly or doing feature-level distillation.
