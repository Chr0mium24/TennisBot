# Multi-Agent Refactor Wave 3 Live3D Core Fixture Review

Date: 2026-06-28

Lead agent: main thread

Source plan:
[`multi_agent_refactor_wave3_live3d_core_fixture_plan_20260628.md`](multi_agent_refactor_wave3_live3d_core_fixture_plan_20260628.md)

Worker result:
[`multi_agent_refactor_wave3_live3d_core_fixture_result_20260628.md`](multi_agent_refactor_wave3_live3d_core_fixture_result_20260628.md)

## Summary

Wave 3 is merged into `main`. `apps/live3d` fixture mode now uses
contract-shaped fixture detections and in-memory stereo calibration, then calls
the runtime core pipeline:

```text
selectBestStereoPair -> triangulateStereoPair -> predictTrajectory
```

The UI still clearly labels this as fixture mode. It does not validate USB
cameras, real YOLO inference, real calibration artifacts, real stereo tracking,
or real prediction.

## Integration

| Branch | Worker commit | Lead integration |
| --- | --- | --- |
| `refactor/live3d-core-fixture` | `0ea535a` | `7f0f2f8` |

## Lead Review Notes

- The branch only changed `apps/live3d/**` and `docs/**`.
- `packages/core` and `packages/contracts` were consumed read-only.
- The fixture builder computes the latest 3D point from core triangulation
  rather than using hand-coded scene points.
- The fixture prediction samples and landing point come from
  `predictTrajectory`.
- Tests assert that fixture construction produces a stereo match, triangulated
  point, prediction curve, and landing point.

## Verification

Final verification on `main`:

```bash
cd apps/live3d
bun run typecheck
bun test
bun run build
```

Result:

- `3 pass`
- `tsc --noEmit` passed
- browser bundle built successfully

```bash
cd packages/core
bun test
bun run typecheck
```

Result:

- `13 pass`
- `tsc --noEmit` passed

```bash
cd packages/contracts
bun test
bun run typecheck
```

Result:

- `4 pass`
- `tsc --noEmit` passed

```bash
git diff --check HEAD~8..HEAD
```

Result:

- passed with no output

## Remaining Dirty State

The only remaining dirty top-level status after the merge is still:

```text
 m TennisBallDetectorLab
```

This is the pre-existing user-owned YOLO dataset/model state. It was not
modified, staged, or cleaned.

## Next Step

The next practical branch is:

```text
refactor/artifact-loaders
```

Scope:

- add runtime validation/loading helpers for YOLO model package metadata;
- add runtime validation/loading helpers for calibration package metadata;
- convert artifact JSON field names into the `packages/contracts` in-memory
  shape explicitly;
- keep real USB camera and YOLO inference out of scope until loaders are tested.
