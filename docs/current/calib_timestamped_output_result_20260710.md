# Calib Timestamped Output Result

Date: 2026-07-10

## Summary

`scripts/calib.ts` no longer writes normal mono/stereo runs to fixed calibration
package names by default. The default outputs are now timestamped:

- `artifacts/calibration/cam1_<local_timestamp>`
- `artifacts/calibration/cam2_<local_timestamp>`
- `artifacts/calibration/stereo_cam1_cam2_<local_timestamp>`

The stereo wrapper keeps the usual command sequence by selecting the latest
accepted mono package for `cam1` and `cam2` when `--left-mono` / `--right-mono`
are not provided. Explicit `--output` remains available for intentionally
writing a fixed runtime path.

## Verification

Commands run from the repository root:

```bash
bun scripts/calib.ts --help
bun scripts/calib.ts mono --help
bun scripts/calib.ts stereo --help
bun scripts/calib.ts mono cam1 --dry-run
bun scripts/calib.ts mono cam2 --dry-run
bun scripts/calib.ts stereo --dry-run
bun scripts/calib.ts stereo --dry-run --output artifacts/calibration/stereo_cam1_cam2
```

Observed results:

- Mono dry-run printed timestamped output paths such as
  `../../artifacts/calibration/cam1_20260710_154758_CST`.
- Stereo dry-run printed a timestamped output path such as
  `../../artifacts/calibration/stereo_cam1_cam2_20260710_154758_CST`.
- Stereo dry-run selected the current accepted mono packages:
  `../../artifacts/calibration/cam1` and `../../artifacts/calibration/cam2`.
- Explicit `--output artifacts/calibration/stereo_cam1_cam2` still routes the
  solve command to the fixed runtime package path.

No camera capture or calibration solve was executed during verification.

