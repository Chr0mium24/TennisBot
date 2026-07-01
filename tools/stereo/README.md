# TennisBot Stereo GUI

`tools/stereo` is the local OpenCV stereo-coordinate GUI. It opens two USB
cameras, runs tennis-ball detection, rectifies detections with the current
stereo calibration artifact, triangulates the ball in the camera frame, and
shows x/y/z/range plus stereo diagnostics.

Run from the repository root through the launcher:

```bash
bun scripts/stereo.ts gui
```

Record a long run:

```bash
bun scripts/stereo.ts gui --tile --record-run
```

Open the replay frontend:

```bash
bun scripts/stereo.ts replay
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

## Recording Format

Recorded sessions are written under `runs/stereo/<session>/`:

```text
session.json
points.ndjson
detections.ndjson
preview.mp4   # only when --record-preview-video is used
```

The replay frontend lists these directories, loads a selected record, and uses
two UI range sliders to choose a time window. It renders selected 3D points and
a camera-frame prediction curve in the browser. Time-window selection is not
passed through command-line arguments.
