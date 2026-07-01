# Live3D Hardware Verifier Removal Result

## Summary

Removed the standalone Live3D hardware verifier because the project no longer
needs a separate hardware acceptance command.

Changed scope:

- Deleted `apps/live3d/scripts/verify-hardware.ts`.
- Deleted `apps/live3d/scripts/verify-hardware.test.ts`.
- Removed `verify:hardware` from `apps/live3d/package.json`.
- Deleted the current hardware acceptance checklist document.
- Updated current Live3D/operator docs to point operators at browser readiness
  gates instead of a generated acceptance report.

Archive documents were left unchanged as historical records.

## Verification

Commands run in `apps/live3d`:

```bash
bun test
bun run typecheck
bun run build
```

Results:

```text
bun test: 43 passed, 0 failed.
bun run typecheck: passed.
bun run build: passed.
```

Current non-archive references to `verify:hardware`, `verify-hardware`,
`createAcceptanceChecklist`, and `renderReport` are removed.
