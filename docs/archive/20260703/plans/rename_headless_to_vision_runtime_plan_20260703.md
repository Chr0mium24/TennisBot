# Rename Headless To Vision Runtime Plan

Date: 2026-07-03

## Goal

Remove remaining active `headless` naming from the vision runtime code and
operator-facing documentation.

## Naming

- ROS package: `tennisbot_vision_runtime`
- Python package: `tennisbot_vision_runtime`
- Node executable: `vision_runtime_node`
- ROS node name: `vision_runtime`
- Launch file: `vision_runtime.launch.py`
- Config file: `vision_runtime.yaml`
- Bun launcher: `scripts/vision-runtime.ts`

## Scope

- Rename active package directories/files under `src`.
- Update Python imports, setup metadata, resource markers, launch/config
  references, and node class names.
- Rename the Bun launcher and update its generated ROS command.
- Update README, current docs, and active tool docs that mention the old
  headless runtime.
- Leave historical archive content unchanged except this plan/result pair.

## Verification

- Search active source/docs/tools for remaining `headless` naming.
- Run the launcher help and dry-run commands.
- Compile the renamed Python package.
- Run the renamed package unit tests.
- Run whitespace checks and verify the git working tree.
