# Calibration GUI Capture Gate

Date: 2026-06-29

## Change

The Calibration GUI now blocks `Capture frames` until an accepted target
print-check artifact is loaded. This keeps the GUI flow aligned with the real
physical sequence:

1. generate target;
2. print and measure the target;
3. record an accepted print check;
4. capture cam1 mono, cam2 mono, then stereo frames.

The guard is enforced in the command block and again immediately before command
execution, so a stale button state cannot start capture without the accepted
print-check gate.

## Verification

```text
tools/calibration/frontend/review bun test: 23 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
```
