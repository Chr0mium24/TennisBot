# Camera Refactor Phase 4 Calibration Result

Date: 2026-07-19

## Implemented

- Replaced the public calibration surface with `online`/`offline` and
  `mono`/`stereo` dimensions.
- Mono requires `cam1` or `cam2`.
- Online applies the canonical calibration control profile, reports current
  controls, opens the existing ChArUco capture GUI, then solves and exports.
- Offline requires an explicit `--session`, invokes only the existing solver,
  and does not configure/open a camera or GUI.
- Removed brightness, raw preview, generic camera controls,
  `--capture-only`, and `--solve-only` from the public calibration contract.
  The corresponding internal calibration primitives remain available to the
  orchestrated workflow.

The established ChArUco capture quality gates, mono/stereo solvers, accepted
artifact checks, and stereo mono-input selection were not changed.

## Verification

```text
python -m py_compile scripts/calib.py
PASS

uv run scripts/calib.py online mono cam1 --dry-run
PASS; camera profile/show, GUI capture, and solve were printed in order

uv run scripts/calib.py offline mono cam1 --session tools/calibration/captures/local/fixture --dry-run
PASS; only the mono solve command was printed

uv run scripts/calib.py brightness
PASS (expected rejection with usage for the new contract)
```

Physical online calibration was not possible because no cameras were attached.
