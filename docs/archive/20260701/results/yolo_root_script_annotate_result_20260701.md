# YOLO Root Script Annotate Result 2026-07-01

## Summary

Added `scripts/yolo.ts` so the YOLO annotation frontend/backend can be started
from the repository root:

```bash
bun scripts/yolo.ts annotate
```

The script forwards annotate options to `uv run tennisbot-yolo annotate` from
`tools/yolo`, so the no-Torch/CUDA annotation dependency boundary remains
unchanged.

## Changed Files

- `scripts/yolo.ts`
- `README.md`
- `docs/current/architecture.md`
- `docs/current/command_usage.md`
- `tools/yolo/README.md`

## Verification

```bash
bun scripts/yolo.ts --help
bun scripts/yolo.ts annotate --help
cd tools/yolo && uv run pytest -q
git diff --check
```

Result:

```text
bun scripts/yolo.ts --help: passed
bun scripts/yolo.ts annotate --help: passed
tools/yolo pytest: 14 passed
git diff --check: passed
```
