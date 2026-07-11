# Camera Brightness Check

Date: 2026-06-30

## Purpose

Use a quick brightness check to identify which USB camera is dark, for example
when one lens cap is still on or one camera is blocked.

```bash
uv run scripts/calib.py brightness
```

The calibration wrapper captures one grayscale frame from `/dev/video0` and
`/dev/video2` by default and prints average brightness on a 0-255 scale. The
darker device is printed as the likely covered camera.

## Manual Devices

If auto order is wrong or you want to test specific devices:

```bash
uv run scripts/calib.py brightness --devices /dev/video0,/dev/video2
```

Requires `ffmpeg` and `v4l2-ctl` on the machine running the cameras.

## Video Preview And Controls

Open a live stereo preview and tune UVC shutter/brightness before calibration:

```bash
uv run scripts/calib.py preview
```

Open one camera:

```bash
uv run scripts/calib.py preview cam1
uv run scripts/calib.py preview cam2
```

The preview window provides trackbars for `shutter`
(`exposure_time_absolute`) and `brightness`. By default it switches to manual
exposure, captures `3840x2160` at `30 FPS`, and starts from high visibility
values so a camera with a low numeric brightness sample does not appear as a
black preview. It uses `v4l2-ctl` to write the controls and exits with `q` or
`esc`.

## Where Device Parameters Are Used

Calibration:

```bash
uv run scripts/calib.py mono cam1 --device <device>
uv run scripts/calib.py mono cam2 --device <device>
uv run scripts/calib.py stereo --left-device <left> --right-device <right>
```

Before opening the browser runtime, use the calibration preview controls above
to prepare USB camera exposure/gain.
