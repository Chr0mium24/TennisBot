# Core Weighted LS + RANSAC Default Result

Date: 2026-06-30

## Implemented

- `predictTrajectory` now defaults to `method: "auto"`.
- Auto mode behavior:
  - fewer than 5 points: two-frame fixed-gravity fallback;
  - 5 or more points: Weighted LS over the latest 9 points;
  - 6 or more points: RANSAC outlier guard over the latest 12 points, followed
    by Weighted LS over accepted inliers.
- The implementation keeps the current `z` vertical-up coordinate convention.
- Added optional tuning fields for method, window sizes, RANSAC subset size,
  iteration cap, and residual threshold.
- Updated Live3D fixture test expectations so `sourcePointIds` reflect the
  points actually used by the prediction model.

## Verification

```bash
cd packages/core
bun test
bun run typecheck

cd apps/live3d
bun test
bun run typecheck
bun run build
```

Result:

- `packages/core` test: 23 passed, 0 failed.
- `packages/core` typecheck: passed.
- `apps/live3d` test: 45 passed, 0 failed.
- `apps/live3d` typecheck: passed.
- `apps/live3d` build: passed.

## Notes

The default RANSAC threshold is currently `0.12 m`. It is a conservative
runtime default, not a hardware-calibrated value. After real ball passes are
captured, tune this threshold against observed triangulation residuals and
YOLO/matching jump behavior.
