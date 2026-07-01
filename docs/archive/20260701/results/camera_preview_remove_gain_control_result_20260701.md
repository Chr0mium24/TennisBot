# Camera Preview Remove Gain Control Result

## Changes

- Removed preview `--gain` from the Python CLI.
- Removed gain trackbars from the OpenCV preview window.
- Removed gain from preview overlay text.
- Removed gain from preview dry-run JSON.
- Updated Bun preview help text to list only shutter/exposure and brightness.

## Rationale

The camera preview control experiment showed that gain did not materially affect
image brightness on the tested cameras, while `brightness` had a strong effect.
Keeping gain in the preview UI made the controls misleading.

## Verification

```bash
cd tools/calibration
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
uv run camera-calib-lab camera preview --dry-run --devices /dev/video0,/dev/video2
cd ../..
bun scripts/calib.ts preview --help
git diff --check
```

Results:

- Calibration tests: `14 passed in 0.56s`
- Preview dry-run JSON no longer contains `gain`.
- Bun preview help no longer lists `--gain`.
- Diff check passed.
