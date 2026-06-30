# Camera Brightness Check

Date: 2026-06-30

## Purpose

Use a quick brightness check to identify which USB camera is dark, for example
when one lens cap is still on or one camera is blocked.

```bash
bun scripts/calib.ts brightness
```

The calibration wrapper captures one grayscale frame from `/dev/video0` and
`/dev/video2` by default and prints average brightness on a 0-255 scale. The
darker device is printed as the likely covered camera.

## Manual Devices

If auto order is wrong or you want to test specific devices:

```bash
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
```

Requires `ffmpeg` and `v4l2-ctl` on the machine running the cameras.

## Where Device Parameters Are Used

Calibration:

```bash
bun scripts/calib.ts mono cam1 --device <device>
bun scripts/calib.ts mono cam2 --device <device>
bun scripts/calib.ts stereo --left-device <left> --right-device <right>
```

Live3D hardware verifier UVC preparation:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --uvc-devices <left>,<right>
```
