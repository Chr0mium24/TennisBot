# YOLO Annotator Exclude Advance Plan 2026-07-01

## Goal

Change the YOLO annotation shortcut so pressing `X` on a usable sample marks it
excluded and advances to the next image.

## Behavior

- Marking a sample excluded should move to the next image after the backend
  writes `excluded_images.txt`.
- Restoring an excluded sample should stay on the current image.
- The last image should stay selected after being marked excluded.

## Scope

- Update the static annotator frontend only.
- Do not change label file format, excluded file format, or backend API shape.
