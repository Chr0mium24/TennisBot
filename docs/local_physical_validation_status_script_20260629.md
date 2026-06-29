# Local Physical Validation Status Script

Date: 2026-06-29

## Change

Added `scripts/physical-validation-status.ts` to audit the physical acceptance
state after software preflight.

The script checks:

- generated ChArUco target metadata;
- recorded printed target square measurement;
- real `cam1` mono calibration package;
- real `cam2` mono calibration package;
- real stereo calibration package, gated by the real `cam1` and `cam2` mono
  prerequisites;
- Live3D hardware report reaching `prediction-ready`.

## Result Semantics

The script exits `0` only when every physical gate passes. Until then it exits
non-zero and writes a Markdown report with the next action for each incomplete
gate.

This is stricter than `operator-preflight`, which only checks local software,
artifact, and device readiness.

## Command

```bash
bun scripts/physical-validation-status.ts --output docs/local_physical_validation_status_YYYYMMDD.md
```

## Verification

Observed on 2026-06-29:

```text
physical-validation-status: wrote docs/local_physical_validation_status_20260629.md and exited non-zero because physical gates remain incomplete.
stereo gate: blocked while cam1/cam2 mono packages are still dry-run, even though the current stereo package is hardware validated.
operator-preflight: passed.
```
