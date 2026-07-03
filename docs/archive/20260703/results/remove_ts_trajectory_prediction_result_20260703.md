# Remove TS Trajectory Prediction Result

Date: 2026-07-03

## Summary

Removed the old TypeScript trajectory prediction implementation from
`packages/core` after the ROS Python trajectory predictor became the active
implementation.

Changed files:

- deleted `packages/core/src/prediction.ts`;
- deleted `packages/core/src/prediction.test.ts`;
- removed prediction exports from `packages/core/src/index.ts`;
- updated current README/architecture/status/headless runtime docs so
  `packages/core` no longer claims trajectory prediction ownership.

`packages/contracts/src/prediction.ts` remains because it defines shared data
contracts, not an algorithm implementation.

## Verification

```bash
cd packages/core && bun test && bun run typecheck
```

Result:

```text
21 pass
0 fail
tsc --noEmit passed
```

```bash
PYTHONPATH=src/tennisbot_headless_vision uv run python -m unittest discover -s src/tennisbot_headless_vision/tests
```

Result:

```text
Ran 4 tests in 0.006s
OK
```

```bash
cd packages/contracts && bun test && bun run typecheck
```

Result:

```text
4 pass
0 fail
tsc --noEmit passed
```
