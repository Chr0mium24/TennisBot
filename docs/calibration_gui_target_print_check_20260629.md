# Calibration GUI Target Print Check

Date: 2026-06-29

## Change

The standalone calibration tool now owns the physical print measurement record:

```bash
uv run tennisbot-calibration target record-print-check --measured-square-mm 15.0
```

The Calibration GUI Target tab exposes the same workflow with:

- measured square size input;
- tolerance input;
- target metadata path;
- output JSON path;
- Markdown report path;
- `Record print check` command button;
- imported print-check status in the workspace gate list.

The target metadata path defaults to the generated DFOptix ChArUco target
metadata. If the target PNG output path changes in the GUI, the print-check
metadata path follows the matching `.json` path so the measured print check
stays bound to the target that was actually generated.

The measured square input now defaults to `0` and the `Record print check`
button stays disabled until a positive measured value is entered. This prevents
accidentally recording a passing 15.0 mm measurement before physically printing
and measuring the target.

## Reason

The physical loop cannot proceed from target generation to camera capture until
the printed square is measured. Keeping this inside `tools/calibration` preserves
the tool boundary and lets the GUI carry the operator through target generation,
print measurement, mono capture, stereo capture, and package verification.

## Verification

Run:

```bash
cd tools/calibration
uv run pytest
cd frontend/review
bun test
bun run build
```

Observed result:

```text
tools/calibration uv run pytest: 22 passed.
tools/calibration/frontend/review bun test: 14 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
tennisbot-calibration target record-print-check --measured-square-mm 15.05 --output /tmp/tennisbot-calibration-print-check.json --output-report /tmp/tennisbot-calibration-print-check.md: accepted=true.
Calibration GUI /api/calibration/run accepted target record-print-check and imported api_print_check_probe.json.
operator-preflight: passed.
physical-validation-status: still blocked on the real default print measurement because the API probe wrote only an ignored probe artifact.
```

Follow-up metadata-path check:

```text
tools/calibration/frontend/review bun test: 16 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
Print Check command now includes --target-metadata.
```

Follow-up explicit-measurement gate check:

```text
tools/calibration/frontend/review bun test: 21 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
```
