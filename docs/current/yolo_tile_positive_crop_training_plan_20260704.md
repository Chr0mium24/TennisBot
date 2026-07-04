# YOLO Tile Positive Crop Training and Recognition Plan - 2026-07-04

## Goal

Improve 4K tennis-ball detection for small far-field balls by training on tile-shaped crops that match runtime tiled inference, instead of relying on full 3840x2160 frames that are heavily downscaled by YOLO `imgsz`.

The plan intentionally avoids synthetic background padding. If a crop cannot fit inside the real source image, that crop candidate is skipped.

## Runtime Target

Primary runtime profile:

- Capture: `3840x2160`
- Tile: `1536x864`
- Tile overlap: `160`
- YOLO `imgsz`: `1280`

Fast fallback profile:

- Capture: `3840x2160`
- Tile: `2048x1152`
- Tile overlap: `160`
- YOLO `imgsz`: `1280`

Accuracy escalation profile:

- Capture: `3840x2160`
- Tile: `1536x864`
- Tile overlap: `160`
- YOLO `imgsz`: `1536`

Training should prioritize the primary profile first. The fallback and escalation profiles are for runtime experiments after a crop-trained model exists.

## New Training Scheme

Train the next model primarily on runtime-shaped tile crops, not full 4K frames.

Training stages:

1. Generate a positive-jitter crop dataset from existing 4K labeled images.
2. Mix in controlled negative crops from real image regions without tennis balls.
3. Optionally add a second pass of copy-paste augmentation only after the real crop dataset works.
4. Train with `imgsz=1280` first, using a tile-shaped dataset generated for `1536x864`.
5. Validate on tile-shaped validation images, not only on full-frame validation images.
6. Promote the model only after runtime tiled recognition improves far-field recall.

Initial training command shape:

```bash
uv run --project tools/yolo --extra detect python - <<'PY'
from pathlib import Path
from ultralytics import YOLO

project = Path("tools/yolo/workspace/runs/training").resolve()
model = YOLO("artifacts/models/tennis_ball_yolo/model.pt")
model.train(
    data="tools/yolo/workspace/runs/positive_crop_1536x864_20260704/data.yaml",
    epochs=40,
    imgsz=1280,
    batch=8,
    device="0",
    workers=8,
    patience=10,
    project=str(project),
    name="positive_crop_1536x864_imgsz1280_20260704",
    seed=44,
    exist_ok=True,
)
PY
```

The exact `batch` can be adjusted after checking GPU memory. If `imgsz=1280` recall is still weak for far-field balls, run a second training trial with `imgsz=1536`.

## Positive Crop Data Generation

Use positive crop jitter rather than full-frame-only training or blind sliding-window enumeration.

For each labeled source image and each tennis-ball bbox:

1. Treat the bbox center as an anchor.
2. Sample desired anchor positions inside the crop, such as:
   - x ratios: `0.20, 0.35, 0.50, 0.65, 0.80`
   - y ratios: `0.20, 0.35, 0.50, 0.65, 0.80`
3. For each desired position `(rx, ry)`, compute the crop origin:
   - `crop_x = ball_cx - rx * tile_width`
   - `crop_y = ball_cy - ry * tile_height`
4. Accept the crop only if:
   - `crop_x >= 0`
   - `crop_y >= 0`
   - `crop_x + tile_width <= image_width`
   - `crop_y + tile_height <= image_height`
   - the anchor bbox is fully inside the crop with a small margin, for example `32` to `64` px
5. Do not clamp invalid crop origins into the image. Invalid desired positions are skipped.
6. Do not pad, reflect, blur-fill, or black-fill image borders.

This means center-frame balls can produce many training crops with the ball at different crop locations, while edge-frame balls naturally produce fewer crops.

## Label Rules

For every accepted crop:

- Recompute YOLO labels in crop-local coordinates.
- The anchor bbox must be fully visible and must be kept.
- Other bboxes fully inside the crop should be kept.
- Other bboxes partially intersecting the crop should be dropped by default for the first implementation, to avoid ambiguous clipped tiny-ball labels.
- Empty crops are valid only for negative samples, not for positive anchor crops.

The first implementation should prefer clean labels over maximizing label count. Partial non-anchor clipping can be revisited after baseline results.

## Negative Samples

Generate negative crops from labeled source images and image regions without tennis-ball bboxes.

Recommended ratio:

- Negative crops: `30%` to `80%` of positive crop count.

Rules:

- Crop must stay fully inside the real source image.
- Crop must not overlap any existing bbox beyond a low IoU threshold, for example `0.01`.
- Negative labels are empty `.txt` files.
- Avoid producing large numbers of near-identical negatives from the same image.

## Dataset Controls

Recommended initial limits:

- Tile size: `1536x864`
- Anchor margin: `48` px
- Desired position grid: 5 x 5 ratios
- Positive crops per bbox: cap at `8` to `12`
- Positive crops per image: cap at `16` to `24`
- Negative crop ratio: `0.5`
- Random jitter around desired ratios: optional `+/- 0.03`, only if crop remains valid
- Avoid repeated crop origins by rounding to a small grid, for example `16` px

The cap prevents a few easy center-ball frames from dominating the dataset.

## New Recognition Scheme

Use tiled YOLO recognition at runtime so the model sees image content at the same scale used during training.

Primary stereo GUI command:

```bash
bun scripts/stereo.ts gui \
  --tile \
  --tile-width 1536 \
  --tile-height 864 \
  --tile-overlap 160 \
  --imgsz 1280 \
  --max-depth-m 25.0
```

Fast fallback recognition profile:

```bash
bun scripts/stereo.ts gui \
  --tile \
  --tile-width 2048 \
  --tile-height 1152 \
  --tile-overlap 160 \
  --imgsz 1280 \
  --max-depth-m 25.0
```

Accuracy escalation recognition profile:

```bash
bun scripts/stereo.ts gui \
  --tile \
  --tile-width 1536 \
  --tile-height 864 \
  --tile-overlap 160 \
  --imgsz 1536 \
  --max-depth-m 25.0
```

First-pass recognition test flow:

1. Capture left and right 4K frames.
2. Split each frame into overlapping tiles using the same tile size used for training.
3. Run YOLO on tiles.
4. Convert tile-local detections back to full-frame coordinates.
5. Keep the current per-camera NMS behavior unchanged for the first test.
6. Run the existing stereo pairing and triangulation path.
7. Record FPS, far-field recall, obvious false positives, and failure frames.

Boundary handling:

- `tile_overlap=160` should be larger than the expected tennis-ball bbox diameter, so a ball cut by one tile edge should appear fully in a neighboring tile.
- Detections near tile borders are acceptable during the first test as long as recall improves and false positives remain understandable.
- Do not add new post-processing before the first test. Record border-related failure frames as experiment observations.

Performance path:

- Baseline first: use the existing tiled implementation in `tools/stereo`.
- If FPS is too low, test the `2048x1152` fallback profile.
- Do not change the recognition pipeline before the first crop-trained model test.

## Implementation Plan

1. Add a crop dataset generator under `tools/yolo`.
   - Proposed CLI: `bun scripts/yolo.ts crops positive-jitter`
   - Python command: `tennisbot-yolo crops positive-jitter`
   - Use `uv` project execution and keep dependencies within existing `augment` extra if OpenCV is needed.
2. Add a TOML config for crop generation.
   - Example path: `tools/yolo/configs/positive_crop.toml`
   - Include image roots, label roots, output root, tile size, margin, caps, ratio grid, negative ratio, seed, and split settings.
3. Generate crop images and YOLO labels.
   - Output `images/`, `labels/`, `train.txt`, `val.txt`, `data.yaml`, `manifest.jsonl`, and `report.md`.
   - Preserve source image references and crop metadata in the manifest.
4. Add focused tests.
   - Valid crop origin math.
   - Invalid crop skip behavior near image borders.
   - Anchor bbox remains fully visible.
   - Label coordinate rewrite.
   - Negative crop exclusion.
5. Train a baseline crop model using the new training scheme.
   - Start with `imgsz=1280`, `batch` based on available GPU memory.
   - Compare against the current full-frame-trained model.
6. Run runtime validation using the new recognition scheme.
   - Test `1536x864 overlap=160 imgsz=1280`.
   - Record detection recall, false positives, and FPS.
   - If recall is insufficient, test `imgsz=1536`.
   - If FPS is insufficient, test `2048x1152 overlap=160 imgsz=1280`.
7. Promote the selected model package only after both training and recognition results are documented.

## Experiment Outputs To Save

Each run should save a Markdown result document under `docs/current` or `docs/archive/<date>/results` with:

- Config path and resolved settings.
- Source image and label counts.
- Generated positive and negative crop counts.
- Train/validation split counts.
- Training command.
- Training metrics.
- Runtime command.
- Runtime FPS and observed recall notes.
- Runtime profile: primary, fast fallback, or accuracy escalation.
- Whether the result came from stereo GUI or offline replay.
- Failure samples or screenshots if available.

## Acceptance Criteria

The crop-trained model is considered useful only if it improves far-field ball recall in tiled 4K runtime without making false positives or FPS unacceptable.

Minimum first-pass criteria:

- 4K tiled runtime can detect tennis balls at materially smaller pixel sizes than the current full-frame-trained model.
- Runtime profile and training profile are documented together.
- First-pass conclusions are limited to YOLO recognition quality and runtime speed.
