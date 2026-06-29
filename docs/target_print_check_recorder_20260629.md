# Target Print Check Recorder

Date: 2026-06-29

## Change

Added `scripts/record-target-print-check.ts` to record the physical paper
target measurement after printing the ChArUco SVG.

## Command

After printing the SVG at 100% scale and measuring one square:

```bash
bun scripts/record-target-print-check.ts --measured-square-mm 15.0
```

The command writes:

- `artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json`
- `docs/calibration_target_print_check_YYYYMMDD.md`

The physical validation status script consumes the JSON artifact.

## Acceptance

Default tolerance is `0.2 mm`. The target print gate passes when the measured
square is within `15.0 +/- 0.2 mm`.

## Verification

Observed on 2026-06-29:

```text
bun scripts/record-target-print-check.ts --help: passed.
bun scripts/record-target-print-check.ts --measured-square-mm 15.0 --output /tmp/tennisbot-print-check.json --report /tmp/tennisbot-print-check.md: accepted=true.
```
