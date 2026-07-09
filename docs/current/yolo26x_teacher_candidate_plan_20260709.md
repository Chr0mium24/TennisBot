# YOLO26x Teacher Candidate Plan - 2026-07-09

## Goal

Train a large offline teacher from `yolo26x.pt` and test whether it can generate
useful tennis-ball candidate annotations for later human review.

This teacher is not a runtime model. It can be slow and large. Its job is to
find candidate boxes for annotation, especially `4-8 px` fixed-exposure balls
that the current runtime model misses.

## Why This Is Useful

The current diagnosis shows that many tiny-ball misses have almost no class-head
response at the ground-truth location. A stronger teacher may help in two ways:

1. provide better pseudo/candidate labels on hard real frames;
2. expose which misses are still invisible even to a large model.

Generated labels must be treated as candidates only. They should be reviewed
before becoming training truth because net lines, court lines, reflections, and
posts are common false-positive sources.

## Remote Setup

Host:

`anilam@10.31.151.120`

Python:

`/home/anilam/Downloads/vision/yolo_training/.venv/bin/python`

YOLO CLI:

`/home/anilam/Downloads/vision/yolo_training/.venv/bin/yolo`

Dataset:

`tools/yolo/workspace/runs/final_trainpool_tiny_fixed_cp_20260708/data.yaml`

Dataset counts on the remote host:

| split | images |
|---|---:|
| train | `12,549` |
| val | `1,390` |
| total | `13,939` |

## Steps

1. Smoke-load `yolo26x.pt`.
2. Run raw pretrained `yolo26x.pt` on the frozen small benchmark to see whether
   COCO `sports ball` pretraining produces any useful tiny-ball candidates.
3. Fine-tune `yolo26x.pt` as a one-class teacher on the current final trainpool.
4. Evaluate the teacher on the frozen final raw benchmark at `imgsz=1536`.
5. Generate candidate-label files from the teacher at low confidence for
   human review, not direct ingestion.

## Initial Training Recipe

The first teacher run should be conservative on memory:

| parameter | value |
|---|---|
| model | `yolo26x.pt` |
| data | final trainpool tiny fixed copy-paste dataset |
| imgsz | `960` |
| batch | start with `4`; reduce to `2` if CUDA OOM |
| epochs | `12` |
| patience | `4` |
| workers | `4` |
| pretrained | true |
| augmentations | keep mosaic/mixup/copy-paste disabled for a clean first comparison |

If the `x` model is too slow or does not fit, fall back to `yolo26l.pt` with the
same data and evaluation. That would still be useful as an offline teacher.

## Success Criteria

The teacher is useful if it improves candidate coverage on the 112-image frozen
small benchmark without exploding false positives:

- higher low-threshold center-hit coverage than current P2 (`49/112` at
  `conf=0.001`, center within `16 px`);
- ideally higher IoU50 recall than current P2 (`26/112` at `conf=0.05`);
- candidate review set remains manageable, with obvious false positives
  inspectable by contact sheet.

Do not promote the teacher to runtime. Use it to produce candidate annotations
and hard-negative review batches.
