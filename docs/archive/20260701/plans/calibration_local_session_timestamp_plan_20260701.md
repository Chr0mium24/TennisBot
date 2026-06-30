# Calibration Local Session Timestamp Plan

## Goal

Use local wall-clock timestamps for human-facing calibration session directory
names while keeping machine-readable JSON timestamps in UTC.

## Scope

1. Update `scripts/calib.ts` so new default capture session directories use
   `YYYYMMDD_HHMMSS_<local timezone abbreviation>`.
2. Rename the latest cam1 capture batch from the UTC-derived directory name to
   the local-time directory name.
3. Update path references in the renamed capture batch and current cam1
   calibration package.
4. Verify dry-run command output and calibration tests.
