# Legacy Simulator Reference Cleanup Plan

## Goal

Remove obsolete references to the retired simulator runtime from the local
TennisBot repository so source and documentation searches describe only the
active ROS and real-chassis architecture.

## Scope

- Remove the two obsolete archived runtime-removal documents whose filenames
  refer to the retired simulator.
- Rewrite historical and current documentation to use generic simulator or
  real-chassis terminology.
- Update project rules, generated report strings, CLI warnings, and tests.
- Do not modify the external control workspace or its separate simulation
  package.

## Validation

- Require a case-insensitive tracked-file content and filename search for the
  retired product name to return zero results.
- Run the scoped vision Python and YOLO test suites affected by string changes.
- Run Python compile checks and `git diff --check`.
- Commit the cleaned worktree.
