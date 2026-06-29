# Camera Brightness Check

Date: 2026-06-29

## Purpose

Use a quick brightness check to identify which USB camera is dark, for example
when one lens cap is still on or one camera is blocked.

```bash
bun scripts/check-camera-brightness.ts
```

The script captures one grayscale frame from the first two USB V4L2 capture
devices and prints average brightness on a 0-255 scale. The darker device is
printed as the likely covered camera.

## Manual Devices

If auto order is wrong or you want to test specific devices:

```bash
bun scripts/check-camera-brightness.ts --devices /dev/video0,/dev/video2
```

Requires `ffmpeg` and `v4l2-ctl` on the machine running the cameras.

## Where Device Parameters Are Used

Calibration:

```bash
cd tools/calibration
uv run camera-calib-lab capture charuco-auto-gui --device <device>
uv run camera-calib-lab capture stereo-charuco-auto-gui --left-device <left> --right-device <right>
```

Live3D hardware verifier UVC preparation:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --uvc-devices <left>,<right>
```

Legacy realtime stereo GUI:

```bash
cd desperate/TennisBallDetectorLab
uv run tbl stereo-gui --left-device <left> --right-device <right>
```
