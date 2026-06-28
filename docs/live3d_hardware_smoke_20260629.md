# Live3D Hardware Smoke

Date: 2026-06-29

## Scope

This smoke test validates the current local-machine Live3D path with real USB
cameras, real runtime artifacts, and the browser ONNX backend.

It does not validate final 3D prediction accuracy because the current camera
frames did not contain a detectable tennis ball, and the imported stereo
calibration still has quality warnings.

## Device Enumeration

Command:

```bash
v4l2-ctl --list-devices
```

Result:

```text
USU Camera 4K: usb-0000:00:14.0-4
  /dev/video0
  /dev/video1

USU Camera 4K: usb-0000:00:14.0-5
  /dev/video2
  /dev/video3
```

`/dev/video0` and `/dev/video2` both reported UVC capture support, MJPG
1920x1080, and 30 fps through V4L2.

## Simultaneous Frame Capture

Command:

```bash
mkdir -p artifacts/hardware_smoke/20260629
timeout 15s ffmpeg -hide_banner -loglevel error -y \
  -f v4l2 -input_format mjpeg -video_size 1920x1080 -framerate 30 -i /dev/video0 \
  -f v4l2 -input_format mjpeg -video_size 1920x1080 -framerate 30 -i /dev/video2 \
  -map 0:v:0 -frames:v 1 artifacts/hardware_smoke/20260629/cam0.jpg \
  -map 1:v:0 -frames:v 1 artifacts/hardware_smoke/20260629/cam2.jpg
```

Result:

```text
cam0.jpg: JPEG 1920x1080
cam2.jpg: JPEG 1920x1080
cam0 sha256: fbbac8af600f64242c16d3d685c8c82ef8449134760e5ea6027c7781a7fdb71a
cam2 sha256: f205a6079a723ea8056cfb60ae7967d30a222149347c9a7817cd42cdef1c8af0
cam0 mean/stddev: 1310.8 / 158.457
cam2 mean/stddev: 1414.16 / 251.778
```

The two camera devices can be opened simultaneously outside the browser.

## Live3D Browser Artifact Load

Chrome headless loaded `http://localhost:5178/` through the running Live3D dev
server.

Observed DOM state:

```text
YOLO artifact loaded
Stereo calibration loaded
Baseline: 0.068 m
Start cameras control available
Start YOLO backend control available
```

The artifacts served through Live3D were:

```text
YOLO: dry_run=false, inference_ready=true, default_model=onnx
Calibration: dry_run=false, hardware_validated=true, runtime_quality_warning=true
```

## Browser Camera Open

Chrome was launched with browser media permission auto-approved and controlled
through the Chrome DevTools Protocol.

Result after pressing `Start cameras`:

```text
Left USB camera opened
Right USB camera opened
left video: readyState=4, 1280x720, live track
right video: readyState=4, 1280x720, live track
distinct browser deviceIds: true
YOLO start button enabled: true
```

Both browser video elements received real `MediaStream` tracks from distinct USB
camera devices.

## Browser ONNX YOLO Loop

During the first browser YOLO test, concurrent left/right calls against the same
ONNX Runtime Web session failed with:

```text
Left: Session mismatch
Right: Session already started
```

The Live3D ONNX backend now serializes `session.run()` calls while preserving the
same public backend API. Live3D also runs YOLO continuously after `Start YOLO
backend` until `Stop YOLO adapter` is pressed.

Result after the fix:

```text
Left YOLO updated: onnxruntime-web-yolo produced no tennis-ball detections for this frame.
Right YOLO updated: onnxruntime-web-yolo produced no tennis-ball detections for this frame.
hasSessionError: false
yoloStartDisabled: true
yoloStopDisabled: false
Runtime 3D waiting for left detection
```

The ONNX backend now loads and runs against live browser camera frames. The
current scene did not contain a detectable tennis ball, so this smoke does not
prove the ball detection or runtime 3D prediction visual.

## Verification Commands

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

Result:

```text
39 tests passed.
typecheck passed.
build passed.
```

## Remaining Gates

- Put a tennis ball in both camera views and confirm nonzero runtime detections.
- Confirm runtime 3D scene replaces the fixture fallback.
- Confirm the prediction curve and landing marker update from multiple runtime
  detections.
- Re-run stereo calibration before relying on physical 3D accuracy.
