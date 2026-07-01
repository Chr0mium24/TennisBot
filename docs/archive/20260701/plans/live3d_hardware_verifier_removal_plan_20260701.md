# Live3D Hardware Verifier Removal Plan

## Decision

The standalone Live3D hardware acceptance command is no longer needed. Remove
the dedicated verifier instead of splitting it into smaller modules.

## Scope

- Delete `apps/live3d/scripts/verify-hardware.ts`.
- Delete tests that only cover the verifier report/checklist.
- Remove the `verify:hardware` package script.
- Remove current documentation that instructs operators to run the verifier.
- Keep archive documents unchanged as historical records.

## Verification

After removal, run the Live3D test, typecheck, and build commands to confirm the
remaining app still works without the deleted script.
