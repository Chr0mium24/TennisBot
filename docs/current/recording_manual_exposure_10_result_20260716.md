# Recording Manual Exposure 10 Result

Date: 2026-07-16

## Result

- Default exposure mode remains `auto_exposure=1`, which selects manual
  exposure for the target V4L2 cameras.
- Default `exposure_time_absolute` changed from 200 to 10.
- Other capture and camera controls are unchanged.

## Verification

```bash
cd tools/recording
uv run pytest
```

Result: `9 passed in 0.05s`.

No camera device was available, so the configuration and generated control
commands were verified without applying them to physical hardware.
