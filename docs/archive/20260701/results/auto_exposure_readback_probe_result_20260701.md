# Auto Exposure Readback Probe Result

## Result

Both cameras stayed at `exposure_time_absolute=200` throughout streaming while
`auto_exposure=3` was active.

## Measurements

```text
/dev/video0
  final_auto_exposure=3 (Aperture Priority Mode)
  final_exposure_time_absolute=200
  final_brightness=64
  final_mean_gray=183.67
  frame=01 exposure_time_absolute=200
  frame=10 exposure_time_absolute=200
  frame=30 exposure_time_absolute=200
  frame=60 exposure_time_absolute=200
  frame=90 exposure_time_absolute=200

/dev/video2
  final_auto_exposure=3 (Aperture Priority Mode)
  final_exposure_time_absolute=200
  final_brightness=64
  final_mean_gray=195.56
  frame=01 exposure_time_absolute=200
  frame=10 exposure_time_absolute=200
  frame=30 exposure_time_absolute=200
  frame=60 exposure_time_absolute=200
  frame=90 exposure_time_absolute=200
```

## Interpretation

For the current scene and camera state, auto exposure reports a stable
`exposure_time_absolute=200`. Since previous control experiments showed manual
`exposure_time_absolute=200` is darker than auto exposure at the same readback,
this readback does not fully explain the auto-exposure image processing path.

## Photo Comparison

Saved images:

```text
artifacts/calibration_experiments/auto_vs_manual_exposure_20260701/
```

Measurements:

```text
auto_exposure=3, brightness=64
  /dev/video0 mean_gray=192.88 exposure_time_absolute=200
  /dev/video2 mean_gray=199.11 exposure_time_absolute=200

manual auto_exposure=1, exposure_time_absolute=200, brightness=64
  /dev/video0 mean_gray=131.21 exposure_time_absolute=200
  /dev/video2 mean_gray=134.75 exposure_time_absolute=200
```

Photo comparison confirms that auto exposure at readback `200` is much brighter
than manual exposure at the same readback. For these cameras, the readback value
does not represent the complete auto-exposure imaging behavior.
