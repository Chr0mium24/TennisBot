# Current Docs Archive Reclassification Plan

Date: 2026-07-03

## Goal

Keep `docs/current/` limited to durable current facts and operating guides.
Move dated one-off plans, results, migrations, calibration notes, and YOLO
experiment records into `docs/archive/20260703/` category folders.

## Classification

Keep in `docs/current/`:

- architecture and current status documents;
- headless runtime target and runbook documents;
- command usage and hardware/device guides;
- current YOLO usage guides.

Move to archive categories:

- calibration artifact tracking -> `calibration/`;
- runtime HSV removal -> `results/`;
- YOLO workspace migration -> `migrations/`;
- YOLO backup, label merge, sprite review, and training trial records ->
  `yolo/`.

## Verification

- List `docs/current/` after the move and confirm no dated one-off records
  remain there.
- Search for stale references to moved `docs/current/*_20260703.md` paths.
- Run `git diff --check`.
