# Camera Device Detection

Date: 2026-06-29

## Purpose

USB camera `/dev/videoN` numbers can change when cameras move between ports.
Use the local detector before calibration or hardware verification:

```bash
bun scripts/detect-camera-devices.ts
bun scripts/detect-camera-devices.ts --json
```

The script lists V4L2 capture devices, `/dev/v4l/by-id` and
`/dev/v4l/by-path` symlinks when available, and suggested left/right command
arguments.

## Where To Pass Devices

Calibration mono:

```bash
cd tools/calibration
uv run camera-calib-lab capture charuco-auto-gui --device <left-or-right-device>
```

Calibration stereo:

```bash
cd tools/calibration
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --left-device <left-device> \
  --right-device <right-device>
```

Live3D hardware verifier UVC preparation:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --uvc-devices <left-device>,<right-device>
```

Legacy TennisBallDetectorLab realtime stereo GUI:

```bash
cd desperate/TennisBallDetectorLab
uv run tbl stereo-gui --left-device <left-device> --right-device <right-device>
```

## Live3D Browser UI

The browser cannot directly use `/dev/videoN` paths. Live3D selects browser
camera inputs through browser `deviceId` or labels. The detector still matters
for OS-side UVC control preparation and for all OpenCV tools.

## Limitation

If two identical cameras expose the same USB name and no unique
`/dev/v4l/by-id` symlinks, software cannot prove which physical camera is left
after moving USB ports. In that case, use the script output as a starting point
and verify left/right visually before calibration or validation.
