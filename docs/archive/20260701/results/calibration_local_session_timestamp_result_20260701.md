# Calibration Local Session Timestamp Result

## Changes

- Updated `scripts/calib.ts` default session naming from UTC-derived
  `YYYYMMDDHHMMSS` to local `YYYYMMDD_HHMMSS_<timezone>`.
- Renamed the latest cam1 capture batch on disk:
  - from `tools/calibration/captures/local/cam1_charuco_20260630233211`
  - to `tools/calibration/captures/local/cam1_charuco_20260701_073211_CST`
- Rewrote path references inside the renamed capture batch and current
  `artifacts/calibration/cam1` package to the new session directory.
- Kept JSON `created_at` values in UTC.

## Notes

- `tools/calibration/captures/` and `artifacts/` are gitignored local
  artifacts, so the on-disk batch rename is not part of the git commit.

## Verification

```bash
bun scripts/calib.ts mono cam1 --dry-run
bun scripts/calib.ts mono cam1 --solve-only --dry-run
bun scripts/calib.ts stereo --dry-run
cd tools/calibration
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
```

Results:

- New capture dry-run path format:
  `captures/local/cam1_charuco_20260701_074601_CST`
- `mono cam1 --solve-only --dry-run` resolved the renamed latest session:
  `captures/local/cam1_charuco_20260701_073211_CST`
- Calibration tests: `11 passed in 0.48s`
