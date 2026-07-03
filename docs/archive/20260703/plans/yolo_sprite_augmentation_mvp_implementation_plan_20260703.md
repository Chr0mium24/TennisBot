# YOLO Sprite Augmentation MVP Implementation Plan 2026-07-03

## Goal

Implement the first usable `tools/yolo` workflow for reviewed ball sprites and
copy-paste augmentation.

## Scope

1. Keep the existing bbox annotator unchanged.
2. Add `tennisbot-yolo sprites extract` to create ellipse-mask sprite
   candidates from existing YOLO bbox labels.
3. Add `tennisbot-yolo sprites review` with a local HTML page for mask editing
   and approve/reject decisions.
4. Add `tennisbot-yolo augment copy-paste` with a shared
   `configs/augmentation.toml` file.
5. Expose the new commands from `bun scripts/yolo.ts`.
6. Add focused tests for bbox parsing, sprite metadata, and copy-paste label
   generation.

## Defaults

- Approved sprites are copied into an `approved/` directory.
- Backgrounds prefer empty-label or unlabeled images but may use labeled
  images while preserving their original labels.
- Whole source images are not rotated, tilted, sheared, or perspective warped.
- Ball-only transforms may include scale, brightness, contrast, small rotation,
  and light motion blur.
- Pasted ball bboxes are recalculated from the final visible alpha mask.
- Generated data is written under `tools/yolo/yolo/runs/` and source datasets
  are not modified.

## Non-Goals

- Do not train YOLO in this change.
- Do not add segmentation labels.
- Do not modify Live3D or ROS/Gazebo behavior.
- Do not claim detector accuracy improvements before a later training and
  validation experiment.
