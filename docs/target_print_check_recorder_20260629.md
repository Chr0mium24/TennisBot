# Target Print Check Recorder

Date: 2026-06-29

## Change

Added calibration target print-check recording to the standalone calibration
tool and Calibration GUI. The root `scripts/record-target-print-check.ts`
remains as a convenience wrapper, but the primary workflow is now
`tennisbot-calibration target record-print-check`.

## Command

After printing the SVG at 100% scale and measuring one square:

```bash
cd tools/calibration
uv run tennisbot-calibration target record-print-check --measured-square-mm 15.0
```

The command writes:

- `artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json`
- `docs/calibration_target_print_check_YYYYMMDD.md`

The physical validation status script consumes the JSON artifact.
The Calibration GUI Target tab exposes the same command as `Record print
check`.

## Acceptance

Default tolerance is `0.2 mm`. The target print gate passes when the measured
square is within `15.0 +/- 0.2 mm`.

## Verification

Observed on 2026-06-29:

```text
uv run tennisbot-calibration target record-print-check --measured-square-mm 15.05 --output /tmp/print_check.json --output-report /tmp/print_check.md: accepted=true.
bun scripts/record-target-print-check.ts --help: passed.
bun scripts/record-target-print-check.ts --measured-square-mm 15.0 --output /tmp/tennisbot-print-check.json --report /tmp/tennisbot-print-check.md: accepted=true.
```
