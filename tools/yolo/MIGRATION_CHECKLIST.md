# TennisBallDetectorLab To tools/yolo Migration Checklist

Date: 2026-06-28

This checklist is for a later migration wave. Do not perform these moves while
`TennisBallDetectorLab/yolo/dataset` has user-owned dirty changes.

## Preconditions

- The lead confirms no active user-owned edits under
  `TennisBallDetectorLab/yolo/dataset/`.
- The lead confirms whether `TennisBallDetectorLab` remains a nested Git
  checkout, becomes ordinary tracked files, or is replaced by copied source.
- `apps/live3d` has a documented model package loader target.
- `artifacts/models/` is ignored and ready for generated package outputs.
- A small fixture package is approved if tests need one; do not commit real
  `.pt`, `.onnx`, `.rknn`, or large datasets.

## Move Order

1. Move Python CLI/package code from
   `TennisBallDetectorLab/src/tennis_ball_detector_lab/` into a future
   `tools/yolo/src/tennisbot_yolo/` package.
2. Rename the console command from `tbl` to `tennisbot-yolo`, or keep `tbl` as
   a temporary compatibility alias.
3. Move focused tests from `TennisBallDetectorLab/tests/` to
   `tools/yolo/tests/`, excluding tests that require local datasets or model
   artifacts.
4. Move `TennisBallDetectorLab/web/yolo-annotator/` to
   `tools/yolo/web/yolo-annotator/` and keep TypeScript commands on `bun`.
5. Move lightweight configs from `TennisBallDetectorLab/yolo/configs/` and
   `TennisBallDetectorLab/yolo/dataset_configs/` only after checking whether
   they reference local absolute paths or dirty dataset content.
6. Convert direct `yolo/scripts/*.py` entrypoints into CLI subcommands or
   temporary shims under `tools/yolo/scripts/`.
7. Update package export so the canonical runtime output is
   `artifacts/models/tennis_ball_yolo/` and follows
   `MODEL_PACKAGE_CONTRACT.md`.
8. Update docs to point users at `tools/yolo` commands.
9. Run Python tests with `uv` and annotator checks with `bun`.
10. Remove compatibility aliases only after downstream consumers stop using
    `TennisBallDetectorLab` paths.

## Files To Keep Out Of Git Moves

Do not move or rewrite these in the migration unless the lead explicitly
coordinates artifact handling:

- `TennisBallDetectorLab/yolo/dataset/**`;
- `TennisBallDetectorLab/yolo/runs/**`;
- `TennisBallDetectorLab/yolo/models/**`;
- `TennisBallDetectorLab/detector_package/**`;
- `TennisBallDetectorLab/model_packages/**`;
- local `.pt`, `.onnx`, `.rknn`, `.engine`, `.bin`, or similar model outputs.

## Compatibility Tasks

- Preserve `--allow-missing-images` for checkout validation without local image
  folders.
- Preserve backend annotator atomic label writes.
- Preserve the single class id `0 = tennis_ball`.
- Preserve RKNN export dependency pins until RKNN-Toolkit2 compatibility is
  retested.
- Keep current HSV and realtime stereo GUI behavior out of `tools/yolo` unless
  it is explicitly split into runtime diagnostics; the real live app belongs
  under `apps/live3d`.

## Acceptance Gates

- `uv run pytest tools/yolo/tests` passes.
- `cd tools/yolo/web/yolo-annotator && bun run check` passes when the web tool
  has migrated.
- `uv run tennisbot-yolo validate-dataset --allow-missing-images` works on a
  checkout without local images.
- `uv run tennisbot-yolo package --output-dir artifacts/models/tennis_ball_yolo`
  produces a package that `apps/live3d` can validate without importing tool
  internals.
- No dataset labels, generated runs, or large model artifacts are modified by
  the migration commit.
