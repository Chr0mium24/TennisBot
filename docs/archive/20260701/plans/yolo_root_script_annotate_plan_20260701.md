# YOLO Root Script Annotate Plan 2026-07-01

## Goal

Add a repository-root Bun script entry for starting the YOLO annotation
frontend/backend without changing into `tools/yolo`.

## Scope

1. Add `scripts/yolo.ts`.
2. Support `bun scripts/yolo.ts annotate [options]`.
3. Forward annotate options to `uv run tennisbot-yolo annotate`.
4. Document the new entry in current docs and tool README.

## Non-Goals

- Do not add Torch/CUDA dependencies to the annotation path.
- Do not change the annotator API or label/excluded file formats.
