# YOLO Tool Boundary Result

Date: 2026-06-28

Branch: `refactor/yolo-tool-boundary`

## Scope

Created the documentation boundary for future YOLO tooling under
`tools/yolo`. No implementation, dataset, run, or model artifact files were
edited.

## Outputs

- `tools/yolo/README.md`: current `TennisBallDetectorLab` command map to target
  `tools/yolo` commands and runtime boundary notes.
- `tools/yolo/MODEL_PACKAGE_CONTRACT.md`: model package contract consumed by
  `apps/live3d`.
- `tools/yolo/MIGRATION_CHECKLIST.md`: later migration checklist for moving
  `TennisBallDetectorLab` safely.

## Verification Results

This branch is documentation-only. Verification run after staging and commit:

- `git diff --cached --check`: passed before commit with no output.
- `git diff --cached --name-only | rg '^(TennisBallDetectorLab/yolo/(dataset|runs|models)/|TennisBallDetectorLab/yolo26n\.pt$)' || true`: passed with no output.
- `git diff --cached --stat`: showed four Markdown files only.
- `git status --short -- TennisBallDetectorLab/yolo/dataset TennisBallDetectorLab/yolo/runs TennisBallDetectorLab/yolo/models TennisBallDetectorLab/yolo26n.pt`: passed with no output in the isolated branch worktree.
- `git diff-tree --no-commit-id --name-only -r HEAD`: after commit, showed only the four files listed above.

## Notes

`TennisBallDetectorLab` currently has many user-owned dirty YOLO dataset
changes. They are intentionally left as-is and excluded from the commit.
