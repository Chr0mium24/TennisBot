# Remove TS Trajectory Prediction Plan

Date: 2026-07-03

## Goal

Remove the old TypeScript trajectory prediction algorithm after the ROS Python
headless runtime has its parity implementation.

## Scope

- Delete `packages/core/src/prediction.ts`.
- Delete `packages/core/src/prediction.test.ts`.
- Remove prediction exports from `packages/core/src/index.ts`.
- Update current docs so `packages/core` no longer claims ownership of
  trajectory prediction.
- Keep TypeScript data contracts in `packages/contracts` because ROS/interface
  messages and tool schemas still use prediction-shaped data.

## Verification

- Run `packages/core` Bun tests and typecheck.
- Run Python headless trajectory tests to confirm the active ROS predictor still
  passes.
- Save results in a Markdown result document.
