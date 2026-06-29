# Calibration GUI Target Command Bridge Fix

Date: 2026-06-29

## Issue

The Calibration GUI target tab generated this command shape:

```bash
uv run tennisbot-calibration target charuco \
  --output ../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png \
  --output-report ../../docs/calibration_charuco_target_sheet_YYYYMMDD.md \
  --dpi 300 \
  --margin-mm 10
```

The local command bridge allowed the `target charuco` command and listed
`--dpi` plus `--margin-mm` as allowed target flags, but it did not register
those two flags as value flags. The server would reject the first physical
workflow step from the GUI before it could generate the printable target.

## Fix

`--dpi` and `--margin-mm` are now accepted as value flags by the calibration
command bridge. The command runner test covers the target command with both
arguments present.

## Verification

Run from the repository root:

```bash
cd tools/calibration/frontend/review
bun test
bun run build
```

Observed result:

```text
bun test: 12 passed, 0 failed.
bun run build: passed.
```

The restarted local Calibration GUI API also accepted and ran the target command:

```text
status: passed
exitCode: 0
generated: artifacts/calibration_targets/api_target_check.json
report: docs/calibration_target_api_check_20260629.md
```
