# Python/TS Trajectory Parity Result

Date: 2026-07-03

## Summary

The ROS Python headless trajectory predictor now ports the TypeScript
`packages/core` fixed-gravity trajectory selection logic:

- two-frame fallback;
- weighted fixed-gravity least squares;
- RANSAC guarded weighted least squares as the default `auto` path when enough
  samples are available.

The ROS node API remains unchanged: `predict_target(...)` still returns one
target point for `/vision/target_prediction`, and returns no prediction when the
configured target plane is unreachable or outside the configured time window.

## Parity Fixtures

Added Python unit coverage for fixture inputs that match the TypeScript
`packages/core/src/prediction.test.ts` cases:

- two-frame reference prediction;
- weighted LS default prediction;
- RANSAC default prediction with one jumped triangulation point;
- unreachable target plane returning no ROS target.

The numeric target and timing outputs match the TS fixture results for the same
input samples.

## Verification

```bash
PYTHONPATH=src/tennisbot_headless_vision uv run python -m unittest discover -s src/tennisbot_headless_vision/tests
```

Result:

```text
Ran 4 tests in 0.006s
OK
```

```bash
cd packages/core && bun test && bun run typecheck
```

Result:

```text
26 pass
0 fail
tsc --noEmit passed
```

Note: running the Python test command without `PYTHONPATH=src/tennisbot_headless_vision`
does not discover the ROS package from the repository root.
