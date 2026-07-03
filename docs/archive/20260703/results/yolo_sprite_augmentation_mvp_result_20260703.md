# YOLO Sprite Augmentation MVP Result 2026-07-03

## Summary

Implemented the first `tools/yolo` sprite review and copy-paste augmentation
workflow.

## Implemented

- Added `tennisbot-yolo sprites extract` to create transparent sprite
  candidates from existing YOLO bbox labels.
- Added `tennisbot-yolo sprites review` to serve a local HTML review page for
  ellipse/mask editing and approve/reject decisions.
- Added `tennisbot-yolo augment copy-paste` with the shared
  `tools/yolo/configs/augmentation.toml` config.
- Added root Bun script support:
  - `bun scripts/yolo.ts sprites extract`
  - `bun scripts/yolo.ts sprites review`
  - `bun scripts/yolo.ts augment copy-paste`
- Kept augmentation dependencies in the new `augment` optional extra:
  OpenCV/NumPy only, no Torch/CUDA/Ultralytics.
- Added tests for label parsing, sprite extraction, approval copy, and
  generated copy-paste YOLO labels.

## Constraints Preserved

- Existing bbox labels remain the canonical training annotations.
- The review page edits only ellipse/alpha-mask metadata and generated sprite
  PNGs.
- Original source images and labels are not modified by sprite extraction or
  augmentation.
- Whole background images are not rotated, tilted, sheared, or perspective
  warped.
- Pasted ball bboxes are recalculated from the final visible alpha mask.
- Synthetic validation samples are not generated.

## Verification

```bash
bun scripts/yolo.ts --help
bun scripts/yolo.ts sprites extract --help
bun scripts/yolo.ts augment copy-paste --help
bun scripts/yolo.ts sprites review --help
uv run pytest -q
uv run --extra augment pytest -q
python -m compileall -q tools/yolo/src tools/yolo/tests
```

Results:

- Root script help: passed.
- Sprite extract help: passed.
- Sprite review help: passed.
- Copy-paste augment help: passed.
- `uv run pytest -q`: 16 passed.
- `uv run --extra augment pytest -q`: 16 passed.
- Python compileall: passed.

## Follow-Up

- Run sprite extraction against the real local labeled dataset after labels are
  restored under `tools/yolo/yolo/dataset`.
- Use the review page to curate approved sprites before generating any large
  training dataset.
- Train and validate in a separate experiment before claiming detector quality
  changes.
