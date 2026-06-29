# Live3D Hardware Acceptance Checklist

Date: 2026-06-29

## Scope

`apps/live3d/scripts/verify-hardware.ts` now renders a fixed acceptance
checklist in each hardware verification Markdown report. The verifier still
requires `prediction-ready` for a passing hardware run, but the report now
separates software/runtime readiness from external scene blockers such as a
missing visible tennis ball.

## Acceptance Gates

Each generated report includes these gates:

- Live3D app server
- Runtime snapshot export
- YOLO artifact package
- Stereo calibration package
- Stereo USB camera streams
- Readable camera frames
- Left YOLO detection
- Right YOLO detection
- Stereo triangulated ball point
- Prediction curve and landing point

Gate status values are:

- `passed`: the requirement was directly observed.
- `failed`: the verifier observed a runtime/software condition that contradicts
  the requirement.
- `blocked`: the runtime prerequisites passed, but a physical scene condition
  prevents completion.
- `unknown`: upstream gates did not provide enough evidence to judge the
  requirement.

## No-Ball Classification

The current known hardware failure mode is a readable, non-black stereo camera
scene with no visible tennis ball. That now appears as:

```text
blocked: Left YOLO detection
blocked: Right YOLO detection
unknown: Stereo triangulated ball point
unknown: Prediction curve and landing point
```

This is intentionally still an overall failed hardware validation, because the
final requirement is a real `prediction-ready` runtime. The checklist makes the
next action explicit: put a visible tennis ball in both camera views or validate
the model under the current lighting.

## Verification

Commands:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

Result:

```text
bun test: 44 passed, 0 failed.
bun run typecheck: passed.
bun run build: passed.
```

The new tests import the hardware verifier without launching Chrome or cameras,
which is why the command-line entrypoint was guarded with `import.meta.main`.
The actual `bun run verify:hardware` flow remains the same.

## Remaining Field Work

- Capture a visible ChArUco stereo session and solve a fresh mono/mono/stereo
  calibration package.
- Run `bun run verify:hardware -- --prepare-uvc-controls` with a visible tennis
  ball crossing both camera views until the final gate reaches
  `prediction-ready`.
