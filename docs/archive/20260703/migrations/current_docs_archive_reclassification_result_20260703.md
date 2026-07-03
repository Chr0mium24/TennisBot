# Current Docs Archive Reclassification Result

Date: 2026-07-03

## Summary

Moved dated one-off records out of `docs/current/` and into
`docs/archive/20260703/` category folders. `docs/current/` now contains only
durable current-state and operating documents.

## Moved Files

Calibration:

- `docs/current/calibration_artifact_tracking_20260703.md`
  -> `docs/archive/20260703/calibration/calibration_artifact_tracking_20260703.md`

Migrations:

- `docs/current/yolo_workspace_migration_20260703.md`
  -> `docs/archive/20260703/migrations/yolo_workspace_migration_20260703.md`

Results:

- `docs/current/runtime_hsv_removal_20260703.md`
  -> `docs/archive/20260703/results/runtime_hsv_removal_20260703.md`

YOLO:

- `docs/current/yolo_aug1000_training_trial_20260703.md`
  -> `docs/archive/20260703/yolo/yolo_aug1000_training_trial_20260703.md`
- `docs/current/yolo_backup_0260701_dataset_merge_20260703.md`
  -> `docs/archive/20260703/yolo/yolo_backup_0260701_dataset_merge_20260703.md`
- `docs/current/yolo_dataset_backup_label_merge_20260703.md`
  -> `docs/archive/20260703/yolo/yolo_dataset_backup_label_merge_20260703.md`
- `docs/current/yolo_sprite_review_five_point_mask_20260703.md`
  -> `docs/archive/20260703/yolo/yolo_sprite_review_five_point_mask_20260703.md`

## Verification

Remaining `docs/current/` files:

```text
architecture.md
camera_devices.md
chassis_pose_input_gap.md
command_usage.md
headless_ros_vision_runtime.md
how_to_run_zh.md
operator_runbook.md
status.md
yolo_detect_gui.md
yolo_sprite_augmentation_usage.md
```

Checks:

```bash
find docs/current -maxdepth 1 -type f -printf '%f\n' | sort
rg -n "current/(calibration_artifact_tracking_20260703|runtime_hsv_removal_20260703|yolo_aug1000_training_trial_20260703|yolo_backup_0260701_dataset_merge_20260703|yolo_dataset_backup_label_merge_20260703|yolo_sprite_review_five_point_mask_20260703|yolo_workspace_migration_20260703)|docs/current/(calibration_artifact_tracking_20260703|runtime_hsv_removal_20260703|yolo_aug1000_training_trial_20260703|yolo_backup_0260701_dataset_merge_20260703|yolo_dataset_backup_label_merge_20260703|yolo_sprite_review_five_point_mask_20260703|yolo_workspace_migration_20260703)" README.md docs scripts tools packages src .gitignore -g '!docs/archive/20260703/migrations/current_docs_archive_reclassification_result_20260703.md'
git diff --check
```

The stale-path search found no active references after excluding this result
record, which intentionally lists old source paths.
