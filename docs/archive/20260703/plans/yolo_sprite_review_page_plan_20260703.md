# YOLO Sprite Review Page Plan 2026-07-03

## Goal

Add a local "ball sprite review" workflow for `tools/yolo` that keeps the
main training annotation format as YOLO bbox, while allowing the operator to
edit the ellipse/mask used to cut accurate transparent tennis-ball sprites from
already labeled images.

## Operator Workflow

1. Use the existing bbox annotator to label source frames.
2. Run a sprite extraction command that reads YOLO bbox labels and creates
   candidate ball sprites with an initial ellipse mask.
3. Open a local review page to inspect each candidate sprite.
4. Adjust the mask center, radius, ellipse ratio, rotation, and edge feather
   when the automatic mask is not tight enough.
5. Mark each candidate as approved or rejected.
6. Use only approved sprites as inputs for copy-paste augmentation.

## Command Surface

Expose the workflow through both the Python tool and the root Bun wrapper:

```bash
uv run tennisbot-yolo sprites extract
uv run tennisbot-yolo sprites review

bun scripts/yolo.ts sprites extract
bun scripts/yolo.ts sprites review
```

The existing bbox annotation command remains unchanged:

```bash
bun scripts/yolo.ts annotate
```

## Proposed File Layout

```text
tools/yolo/src/tennisbot_yolo/sprites.py
tools/yolo/yolo/scripts/serve_sprite_review.py
tools/yolo/web/yolo-sprite-review/index.html
tools/yolo/yolo/runs/sprites/candidates/
tools/yolo/yolo/runs/sprites/approved/
tools/yolo/yolo/runs/sprites/rejected/
tools/yolo/yolo/runs/sprites/manifest.jsonl
```

Generated sprite outputs stay under `tools/yolo/yolo/runs/` and must not
modify source images or source YOLO labels.

## Data Model

Each sprite candidate should have:

- `sprite.png`: transparent PNG with RGB color and alpha mask.
- `preview.jpg` or preview payload: crop with mask overlay for fast review.
- `sprite.json`: source image path, source label path, source bbox, crop box,
  final ellipse/mask parameters, approval status, and timestamps.

The source YOLO label remains the canonical training annotation:

```text
class_id x_center y_center width height
```

Ellipse/mask metadata is auxiliary data only. It must not replace bbox labels
unless a future YOLO-seg workflow is explicitly planned.

## Extraction Requirements

- Read images from `--images-root` and labels from `--labels-root`, defaulting
  to the current `tools/yolo` dataset paths.
- Skip images listed in `excluded_images.txt`.
- Support nested image and label directories.
- For each positive bbox, crop around the bbox with configurable padding.
- Initialize the alpha mask from the bbox inner ellipse.
- Apply configurable edge feathering to avoid hard paste boundaries.
- Preserve source traceability in `sprite.json`.
- Do not generate candidates from empty negative labels.

## Review Page Requirements

- Static HTML frontend served by a FastAPI backend, matching the current
  annotator deployment style.
- Show the source crop with a semi-transparent mask overlay.
- Show a live transparent-sprite preview against light and dark backgrounds.
- Support keyboard and button actions for previous, next, approve, reject, and
  save.
- Support mask editing:
  - move ellipse center;
  - adjust x/y radius;
  - adjust ellipse rotation;
  - adjust feather width;
  - reset to the bbox-derived default.
- Save edits through backend APIs to local JSON/PNG files.
- Keep approved and rejected decisions durable across page reloads.

## Backend API Shape

The backend should provide simple local-file APIs:

```text
GET  /api/sprites
GET  /api/sprites/{id}
POST /api/sprites/{id}/mask
POST /api/sprites/{id}/approve
POST /api/sprites/{id}/reject
GET  /sprites/{id}.png
GET  /source/{id}
```

The exact route names can change during implementation, but the backend must
not require Torch, Ultralytics, CUDA, or camera access.

## Non-Goals

- Do not change the existing bbox annotation label format.
- Do not add YOLO training in this page.
- Do not add data augmentation in the review page.
- Do not rotate or warp original source images.
- Do not write into validation manifests or model package artifacts.

## Acceptance Criteria

- `bun scripts/yolo.ts annotate` still starts the current bbox annotator.
- `bun scripts/yolo.ts sprites extract --help` and
  `bun scripts/yolo.ts sprites review --help` work from the repo root.
- Extraction creates candidate transparent PNGs and JSON metadata without
  modifying source labels.
- The review page can approve, reject, and edit the mask for a candidate.
- Approved sprites are stored separately from rejected candidates.
- The default dependency path remains no-Torch/no-CUDA.
