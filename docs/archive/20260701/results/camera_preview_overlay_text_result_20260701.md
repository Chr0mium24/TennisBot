# Camera Preview Overlay Text Result

## Changes

- Camera preview now resizes the 4K frame before drawing the overlay text.
- Overlay text is larger, outlined in black, and uses shorter lines:
  - camera/device
  - shutter/gain/brightness
  - mean brightness and quit key
- Stereo preview benefits because each pane gets display-size text instead of
  text that was drawn on 4K input and then scaled down.

## Verification

```bash
cd tools/calibration
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --with pytest python -m pytest -q
cd ../..
bun --check scripts/calib.ts
git diff --check
```

Results:

- Calibration tests: `14 passed in 0.59s`
- Script check passed.
- Diff check passed.
