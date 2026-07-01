# Calibration Concise CLI Output Plan

## Goal

Reduce normal calibration terminal output to the fields needed during capture
and solve: point count, RMS when available, image location, and result path.

## Scope

1. Replace capture and solve JSON stdout with concise one-line summaries.
2. Keep full JSON artifacts written to disk.
3. Keep full command printing only for `bun scripts/calib.ts ... --dry-run`.
4. Add tests that solve stdout is concise and still exposes RMS/result fields.
5. Verify with `bun` and `uv` test commands.
