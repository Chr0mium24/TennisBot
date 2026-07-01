# YOLO Annotator Exclude Advance Result 2026-07-01

## Summary

The YOLO annotator now advances to the next image after `X` marks the current
sample excluded. If `X` restores an already excluded sample, the current image
stays selected. Marking the last image excluded also stays on the last image.

## Changed Files

- `tools/yolo/web/yolo-annotator/index.html`

## Verification

```bash
cd tools/yolo
uv run pytest -q
```

Result:

```text
14 passed
```

```bash
cd tools/yolo/web/yolo-annotator
bun run check
```

Result:

```text
bunx tsc --noEmit
```

```bash
git diff --check
```

Result: passed.

## Notes

The static HTML annotator does not currently have a dedicated browser behavior
test. The change is limited to the existing `toggleExcluded()` success path.
