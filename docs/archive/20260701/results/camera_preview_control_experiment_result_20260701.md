# Camera Preview Control Experiment Result

## Setup

- Devices: `/dev/video0`, `/dev/video2`
- Capture size: `1280x720`
- Saved images: `artifacts/calibration_experiments/preview_controls_20260701/`
- Measurement file: `artifacts/calibration_experiments/preview_controls_20260701/measurements.tsv`

## Key Findings

1. In `auto_exposure=3`, `gain` has almost no visible effect on these cameras.
   - `gain=255`, `brightness=64`: `/dev/video0=184.41`, `/dev/video2=187.49`
   - `gain=32`, `brightness=64`: `/dev/video0=183.19`, `/dev/video2=186.53`
2. In `auto_exposure=3`, `brightness` has a strong effect.
   - `brightness=64`: `/dev/video0=184.41`, `/dev/video2=187.49`
   - `brightness=-5`: `/dev/video0=126.89`, `/dev/video2=131.95`
   - `brightness=-64`: `/dev/video0=72.90`, `/dev/video2=76.29`
3. In `auto_exposure=3`, `exposure_time_absolute` cannot be manually set.
   - Setting exposure to `100` or `200` returned `Permission denied`.
   - Readback stayed at `exposure_time_absolute=200`.
4. In `auto_exposure=1`, manual exposure works, but the same readback value
   is much darker than auto exposure.
   - manual `exposure=100`, `gain=255`, `brightness=64`:
     `/dev/video0=111.91`, `/dev/video2=114.47`
   - manual `exposure=200`, `gain=255`, `brightness=64`:
     `/dev/video0=135.93`, `/dev/video2=139.01`
5. In manual mode, `gain=32` vs `gain=255` at exposure `200` was also nearly
   unchanged in this lighting.
   - `gain=255`: `/dev/video0=135.93`, `/dev/video2=139.01`
   - `gain=32`: `/dev/video0=135.14`, `/dev/video2=137.54`

## Current Restored Camera State

Both devices were restored to:

```text
auto_exposure = 3
exposure_time_absolute = 200
gain = 255
brightness = 64
```

## Interpretation

For these cameras, `brightness` is the effective live brightness control in
auto-exposure preview. `gain` is not useful in the tested conditions, and the
shutter/exposure slider cannot control `exposure_time_absolute` while
`auto_exposure=3` is active.
