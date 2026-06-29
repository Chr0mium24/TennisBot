# Calibration GUI Target File Links

Date: 2026-06-29

## Change

The Calibration GUI target sheet panel now shows direct artifact links for the
generated target files:

- SVG for printing at 100% scale.
- PNG for preview or fallback printing.
- Metadata JSON for audit and import.

The links are derived only from paths under the local `artifacts/` tree served
by the review GUI. Paths outside `artifacts/` are shown as text but are not made
clickable.

## Reason

The next physical step is printing the generated ChArUco target and confirming
one square measures 15.0 mm. Previously the GUI showed target metrics after the
command ran, but the operator still had to locate the generated SVG manually.

## Verification

Run from `tools/calibration/frontend/review`:

```bash
bun test
bun run build
```

Observed result:

```text
bun test: 14 passed, 0 failed.
bun run build: passed.
Calibration GUI HTTP check: / returned 200 and built assets include file-links.
operator-preflight: passed.
```
