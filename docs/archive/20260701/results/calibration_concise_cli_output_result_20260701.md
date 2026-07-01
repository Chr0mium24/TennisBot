# Calibration Concise CLI Output Result

## Changes

- Capture CLI stdout now prints one concise summary line instead of full
  manifest JSON.
- Solve CLI stdout now prints one concise summary line with status, accepted
  view/pair count, point count, RMS, image path pattern, and result path.
- `scripts/calib.ts` no longer prints full commands during normal execution;
  full command printing remains available with `--dry-run`.
- Full manifest/package JSON files are still written to disk.

## Example

```text
solve status=accepted views=40/40 points=104 rms=0.2001px images=/home/cr/Codes/TennisBot/tools/calibration/captures/local/cam1_charuco_20260701_073211_CST/cam1/view*/image.png result=/home/cr/Codes/TennisBot/artifacts/calibration/cam1
```

## Verification

```bash
cd tools/calibration
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
cd ../..
bun scripts/calib.ts mono cam1 --solve-only
git diff --check
```

Results:

- Calibration tests: `13 passed in 0.73s`
- `mono cam1 --solve-only` printed a single solve summary line.
- Diff check passed.
