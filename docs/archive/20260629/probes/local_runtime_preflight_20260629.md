# Local Runtime Preflight

- created_at: 2026-06-29T03:40:35.035Z
- result: passed

## Checks

- passed: Live3D surface - http://127.0.0.1:5178/ returned 200.
- passed: YOLO package - artifacts/models/tennis_ball_yolo verified.
- passed: Stereo calibration package - artifacts/calibration/stereo_cam1_cam2 verified as accepted stereo package.
- passed: USB camera devices - /dev/video0 and /dev/video2 are present.

## Evidence

### Live3D surface

```text
OK
```

### YOLO package

```text
verified=/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo
```

### Stereo calibration package

```text
{
  "accepted": true,
  "details": [],
  "dry_run": false,
  "hardware_validated": true,
  "missing_files": [],
  "package_dir": "../../artifacts/calibration/stereo_cam1_cam2",
  "package_kind": "stereo",
  "schema_version": "calibration.package_verification.v1"
}
```

### USB camera devices

```text
USU Camera 4K:  (usb-0000:00:14.0-4):
	/dev/video0
	/dev/video1
	/dev/media0

USU Camera 4K:  (usb-0000:00:14.0-5):
	/dev/video2
	/dev/video3
	/dev/media1
```
