# YOLO Copy-Paste Augmentation Plan 2026-07-03

## Goal

Add a controlled copy-paste augmentation workflow for `tools/yolo` that uses
reviewed tennis-ball sprites to synthesize extra YOLO detect training images,
without corrupting existing bbox labels or validation data.

## Core Rule

Original labeled images must not receive geometric transforms that would make
their existing bbox labels inaccurate. Whole-image rotation, perspective
tilt, and shear are out of scope for labeled images.

The only optional rotation is a small rotation applied to the reviewed ball
sprite before paste. The pasted ball label is then recalculated from the final
alpha mask.

## Command Surface

Expose augmentation through both the Python tool and the root Bun wrapper:

```bash
uv run tennisbot-yolo augment copy-paste --config tools/yolo/configs/augmentation.toml
bun scripts/yolo.ts augment copy-paste --config tools/yolo/configs/augmentation.toml
```

The command should write a new generated dataset. It must not overwrite the
source dataset.

## Configuration File

Use a shared augmentation config file for repeatability instead of many loose
command-line flags. Do not name the config after only one strategy, because the
same config namespace should be able to hold future augmentation modes. TOML is
preferred because it is readable and easy to edit.

Example:

```toml
[augmentation]
pipeline = "copy_paste"

[inputs]
dataset_root = "tools/yolo/yolo/dataset"
sprites_root = "tools/yolo/yolo/runs/sprites/approved"
excluded_file = "tools/yolo/yolo/dataset/excluded_images.txt"

[output]
root = "tools/yolo/yolo/runs/copy_paste_aug"
count = 3000
seed = 42
image_format = "jpg"
jpeg_quality = 92

[selection]
allow_labeled_backgrounds = true
prefer_negative_backgrounds = true
paste_per_image = [1, 1]
train_only = true

[background]
brightness = [-25, 25]
contrast = [0.85, 1.15]
blur_probability = 0.10
blur_kernel = [3, 5]
rotate_degrees = [0, 0]
perspective = false

[ball]
scale = [0.6, 1.8]
brightness = [-35, 35]
contrast = [0.8, 1.25]
rotate_degrees = [-8, 8]
motion_blur_probability = 0.20
motion_blur_kernel = [3, 9]
alpha_threshold_for_bbox = 16
min_visible_area_px = 12
```

## Augmentation Behavior

For each generated sample:

1. Select a source background image that is not excluded.
2. Load existing labels if the background is labeled.
3. Apply only non-geometric background changes, such as brightness, contrast,
   and optional light blur.
4. Select one or more approved ball sprites.
5. Apply ball-only transforms: scale, brightness, contrast, optional small
   rotation, and optional motion blur.
6. Paste each transformed sprite using its alpha mask.
7. Recalculate the pasted ball bbox from the final alpha mask.
8. Merge original labels with pasted labels when the background already had
   labels.
9. Write the generated image, YOLO label, and manifest row to the output
   dataset.

## Label Accuracy Rules

- Existing source labels can be copied only if the source image receives no
  geometric transform.
- The pasted ball bbox must be recalculated from visible alpha pixels after all
  ball transforms.
- YOLO detect labels remain horizontal axis-aligned boxes.
- Do not write rotated boxes; standard YOLO detect does not support them.
- If a pasted sprite is clipped by image boundaries, compute the bbox from the
  clipped visible alpha mask.
- Drop pasted sprites whose visible alpha area is below the configured minimum.

## Background Selection

The generator should support:

- empty negative labels as preferred clean backgrounds;
- labeled positive images, preserving their original labels;
- optional filtering by camera, session, or nested dataset folder;
- train-only generation to avoid synthetic leakage into validation metrics.

Validation images should not be augmented unless a separate experiment
explicitly requests it.

## Output Layout

```text
tools/yolo/yolo/runs/copy_paste_aug/
  data.yaml
  images/
  labels/
  manifest.jsonl
  config.resolved.toml
  report.md
```

`manifest.jsonl` should record source background, original label file, sprite
ids, random seed state or generated sample index, transforms, pasted bbox, and
output paths.

`report.md` should summarize generated counts, skipped sprites, source
background counts, and parameter ranges.

## Safety Requirements

- Never modify source `images/`, `labels/`, or `excluded_images.txt`.
- Never mix generated files into the default model package artifact.
- Keep the default dependency path lightweight: OpenCV and NumPy are acceptable;
  Torch, Ultralytics, CUDA, and camera access are not required.
- Use deterministic output when the same seed and inputs are provided.
- Fail clearly when no approved sprites or usable background images exist.

## Non-Goals

- Do not add whole-image rotation or perspective tilt for labeled images.
- Do not create segmentation labels.
- Do not train a YOLO model in the augmentation command.
- Do not claim improved accuracy until a separate training and validation
  experiment is run and documented.

## Acceptance Criteria

- The command accepts a config file and writes a resolved config copy.
- Generated images and labels are written to a separate output dataset.
- Original labels remain byte-for-byte unchanged.
- Pasted ball boxes match the final visible alpha mask.
- Empty and labeled backgrounds are both supported.
- A Markdown report is generated with counts and skipped-sample reasons.
- Root wrapper commands under `bun scripts/yolo.ts` expose the same workflow.
