# Calibration GUI Camera Devices Status

Date: 2026-06-29

## Change

The Calibration GUI server now exposes a read-only camera device status endpoint:

```text
GET /api/camera-devices/status
```

The endpoint runs `v4l2-ctl --list-devices`, parses `/dev/video*` groups, and
checks the default real calibration devices:

- `cam1`: `/dev/video0`
- `cam2`: `/dev/video2`

The Capture tab now includes a `Camera Devices` panel with expected device
presence, parsed camera groups, and a refresh button. This lets the operator
confirm the USB camera mapping before running cam1 mono, cam2 mono, or stereo
captures.

## Verification

```text
tools/calibration/frontend/review bun test: 20 passed, 0 failed.
tools/calibration/frontend/review bun run build: passed.
GET http://127.0.0.1:5188/api/camera-devices/status: returned schema tennisbot.camera_devices_status.v1 and result passed.
Expected devices present: /dev/video0 and /dev/video2.
Detected groups: USU Camera 4K on /dev/video0,/dev/video1 and USU Camera 4K on /dev/video2,/dev/video3.
bun scripts/start-local-runtime.ts --status: Live3D and Calibration GUI ready.
```
