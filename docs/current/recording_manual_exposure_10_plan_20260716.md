# Recording Manual Exposure 10 Plan

Date: 2026-07-16

## Goal

Set the default recording camera controls to manual exposure with
`exposure_time_absolute=10`.

## Steps

1. Keep `auto_exposure=1`, the V4L2 manual exposure mode used by these cameras.
2. Change the default exposure time from 200 to 10.
3. Update configuration assertions and run the recording test suite with `uv`.

