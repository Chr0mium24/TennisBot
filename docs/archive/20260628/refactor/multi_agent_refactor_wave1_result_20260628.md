# Multi-Agent Refactor Wave 1 Result

Date: 2026-06-28

Lead agent: main thread

Source plan:
[`multi_agent_refactor_tasks_20260628.md`](multi_agent_refactor_tasks_20260628.md)

## Summary

Wave 1 is merged into `main`. It created the initial boundaries for:

- `packages/contracts`;
- `packages/core`;
- `tools/calibration`;
- `tools/yolo`;
- `apps/live3d`;
- simulation and legacy runtime audit documentation.

The current work is still a preparation layer. `apps/live3d` is fixture-mode UI
only; it does not open real cameras, run YOLO, triangulate, or validate
prediction yet.

## Branch Results

| Agent | Branch | Worker commit | Lead integration |
| --- | --- | --- | --- |
| A | `refactor/contracts-core-skeleton` | `a6fac3a` | merged with `34cba1c` |
| C | `refactor/calibration-tool-boundary` | `2fe1b65` | cherry-picked as `50eb36b` |
| D | `refactor/yolo-tool-boundary` | `37e32b0` | merged with `fadf451` |
| B | `refactor/live3d-shell` | `41482cd` | merged with `e8b77a2` |
| E | `refactor/sim-runtime-audit` | `697112d` | merged with `dd68484` |

Agent C's branch head also contained a duplicated contracts/core commit
(`88fd1f4`) that was not part of the worker's final reported scope. The lead
did not merge that branch head. Only the clean calibration boundary commit
`2fe1b65` was accepted.

## Files Added By Area

### Contracts And Core

- `packages/contracts/**`
- `packages/core/**`
- `docs/contracts_core_skeleton_plan_result_20260628.md`

These packages define plain TypeScript data contracts and conservative core API
placeholders. Triangulation and prediction intentionally return
`not-implemented` until BallTrajectoryLab logic is migrated behind tests.

### Calibration Boundary

- `tools/calibration/README.md`
- `tools/calibration/artifact_contracts.md`
- `docs/calibration_tool_boundary_result_20260628.md`

This is documentation and artifact-contract work only. `CameraCalibLab` remains
untouched and remains the current working implementation.

### YOLO Boundary

- `tools/yolo/README.md`
- `tools/yolo/MODEL_PACKAGE_CONTRACT.md`
- `tools/yolo/MIGRATION_CHECKLIST.md`
- `docs/yolo_tool_boundary_result_20260628.md`

This is documentation and model-package contract work only. The dirty
`TennisBallDetectorLab/yolo/dataset`, `runs`, and `models` paths were not
edited, moved, or staged.

### Live3D Shell

- `apps/live3d/**`
- `docs/live3d_app_shell_20260628.md`

This creates a TypeScript/Bun static frontend shell with two camera panels,
YOLO-style overlay placeholders, 3D fixture scene, and runtime status panel.
Fixture mode is visibly labeled as non-validating.

### Simulation Runtime Audit

- `docs/sim_runtime_audit_20260628.md`

This audit identifies which TennisWebSim, BallTrajectoryLab, and TennisBotCV
parts should become `apps/sim`, `packages/core`, `packages/contracts`, or
retired legacy content.

## Verification

Final verification on `main`:

```bash
cd packages/contracts
bun test
bun run typecheck
```

Result:

- `3 pass`
- `tsc --noEmit` passed

```bash
cd packages/core
bun test
bun run typecheck
```

Result:

- `5 pass`
- `tsc --noEmit` passed

```bash
cd apps/live3d
bun run typecheck
bun test
bun run build
```

Result:

- `2 pass`
- `tsc --noEmit` passed
- browser bundle built successfully

Whitespace verification:

```bash
git diff --check HEAD~10..HEAD
```

Result:

- passed with no output

The Live3D worker left a temporary `bun` server on port `5178`; the lead stopped
that process after review.

## Remaining Dirty State

The only remaining dirty top-level status after Wave 1 is:

```text
 m TennisBallDetectorLab
```

This was present before Wave 1 and contains user-owned YOLO dataset/model
changes. It was intentionally not modified or cleaned by the merge.

## Review Notes

- Some artifact documentation uses package-file JSON naming such as
  `image_size`, `timestamp_ns`, and `width`/`height`, while the new runtime
  TypeScript contracts use camelCase names such as `imageSize`,
  `timestampUnixMs`, and `widthPx`/`heightPx`.
- This is acceptable for Wave 1 because artifact JSON and runtime in-memory
  contracts can differ if loaders perform explicit conversion.
- Wave 2 should either:
  - add explicit artifact-to-runtime loader contracts, or
  - align artifact JSON field names with `packages/contracts`.

## Next Wave Recommendation

Start Wave 2 with one branch only:

```text
refactor/core-migration
```

Initial scope:

- migrate pure projection/triangulation math from `BallTrajectoryLab` into
  `packages/core`;
- keep Python source read-only until the target TypeScript or cross-language
  strategy is decided;
- add tests using small calibration/detection fixtures;
- do not move YOLO datasets or calibration implementation yet.

After that, move the tools and sim app in separate serial branches.
