# YOLO Stretch and Frame Rotation Augmentation Plan 2026-07-03

## Goal

Extend the copy-paste augmentation MVP with two controlled transforms:

- slight anisotropic stretch on pasted ball sprites;
- slight whole-frame rotation on generated images to simulate camera roll or
  small camera shake.

## Label Rule

Whole-frame rotation is allowed only on generated augmentation outputs. After
rotation, every label in the generated image must be transformed from its four
box corners and rewritten as a standard horizontal YOLO detect bbox.

## Scope

1. Add `ball.stretch_x` and `ball.stretch_y` ranges to
   `tools/yolo/configs/augmentation.toml`.
2. Add a `[frame]` section with `rotate_probability` and `rotate_degrees`.
3. Apply sprite stretch before paste.
4. Apply whole-frame rotation after paste and before writing output.
5. Recalculate all output bboxes after whole-frame rotation.
6. Update tests and Chinese usage docs.

## Non-Goals

- Do not add rotated-box labels.
- Do not rotate original source files in place.
- Do not generate validation data from synthetic rotations.
