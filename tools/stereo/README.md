# TennisBot Stereo GUI

`tools/stereo` is the local OpenCV stereo-coordinate GUI. It opens two USB
cameras, runs tennis-ball detection, rectifies detections with the current
stereo calibration artifact, triangulates the ball in the camera frame, and
shows x/y/z/range plus stereo diagnostics.

Run from the repository root through the launcher:

```bash
bun scripts/stereo.ts gui
```

Direct tool command:

```bash
cd tools/stereo
uv run --extra detect tennisbot-stereo gui --tile
```

Default runtime inputs:

```text
artifacts/calibration/stereo_cam1_cam2
artifacts/models/tennis_ball_yolo/model.pt
/dev/video0,/dev/video2
3840x2160@30 MJPG
```

The reported 3D point is in the left camera frame: x right, y down, z forward.
It is not a tennis-court world coordinate.
