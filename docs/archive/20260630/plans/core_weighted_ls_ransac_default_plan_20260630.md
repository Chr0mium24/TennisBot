# Core Weighted LS + RANSAC Default Plan

Date: 2026-06-30

## Goal

Make `packages/core` trajectory prediction default to the trajectory selection
recommendation: Weighted LS9 as the primary fit with RANSAC outlier protection,
while preserving a safe fallback for short tracks.

## Scope

- Extend `predictTrajectory` without changing the Live3D call site.
- Keep the current z-up coordinate convention:
  `x` lateral, `y` forward/depth, `z` vertical-up.
- Use fixed gravity in negative `z`.
- Use the current two-frame predictor only as the fallback when fewer than five
  usable points are available.
- Add focused Bun tests for default robust prediction, outlier rejection, and
  explicit two-frame compatibility.

## Intended Default

- `method: "auto"` by default.
- `< 5` points: two-frame velocity fallback.
- `>= 5` points: Weighted LS over the latest 9 points.
- `>= 6` points: RANSAC guard over the latest 12 points, then Weighted LS over
  the accepted inliers.

## Verification

- `cd packages/core && bun test`
- `cd packages/core && bun run typecheck`
- `cd apps/live3d && bun test`
- `cd apps/live3d && bun run typecheck`
