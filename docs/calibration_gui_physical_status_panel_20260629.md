# Calibration GUI Physical Status Panel

Date: 2026-06-29

## Change

The Calibration GUI server now exposes a local read-only physical validation
status endpoint:

```text
GET /api/physical/status
```

The endpoint runs `scripts/physical-validation-status.ts` with `/tmp` Markdown
and JSON outputs, then returns the JSON payload to the browser.

The Calibration GUI sidebar now shows:

- physical validation result;
- current next action;
- incomplete gate count;
- refresh button.

After any calibration command runs, the GUI refreshes the physical status so the
sidebar reflects newly generated artifacts such as the target print check.

## Verification

```text
tools/calibration/frontend/review bun test: 16 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
GET http://127.0.0.1:5188/api/physical/status: returned schema tennisbot.physical_validation_status.v1, result incomplete, 6 gates.
operator-preflight: passed.
```
