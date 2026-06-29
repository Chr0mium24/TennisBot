# Live3D Hardware Loop Verification

- Started: 2026-06-28T21:26:09.199Z
- Finished: 2026-06-28T21:26:32.773Z
- App URL: http://localhost:5178
- Result: failed
- Error: Runtime 3D prediction did not reach ready.

## Steps

- passed: app server - http://localhost:5178 is already serving Live3D.
- passed: chrome - /usr/bin/google-chrome is listening on CDP port 9233.
- passed: chrome tab - Opened http://localhost:5178.
- passed: page snapshot - window.__tennisbotLive3dSnapshot is available.
- passed: camera startup - 2 video input(s); left=USU Camera 4K: (a000:b111); right=USU Camera 4K: (a000:b111).
- failed: runtime 3D prediction - Left YOLO never produced a tennis-ball detection.
- passed: frame capture - Saved 2 video frame capture(s) under /home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_frames.
- failed: frame quality - left, right capture(s) are near-black; check camera exposure, lens cover, or browser capture backend before judging YOLO.

## Observations

- Snapshots seen: 16
- Max left detections: 0
- Max right detections: 0
- Max trail length: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing

## Frame Captures

- saved: left - 1280x720 PNG frame via image-capture; mean luma 0.00, max luma 0.00, non-black 0.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_frames/left.png)
- saved: right - 1280x720 PNG frame via image-capture; mean luma 0.00, max luma 0.00, non-black 0.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_frames/right.png)

## Direct V4L2 Cross-Check

- `timeout 5s ffmpeg ... -i /dev/video0 -frames:v 1 .../video0.jpg`: exit `124`, no JPEG written.
- `timeout 5s ffmpeg ... -i /dev/video2 -frames:v 1 .../video2.jpg`: exit `124`, no JPEG written.
- `timeout 5s v4l2-ctl -d /dev/video0 --stream-mmap --stream-count=1 --stream-to=.../video0.raw`: exit `124`, 0-byte raw file.
- `timeout 5s v4l2-ctl -d /dev/video2 --stream-mmap --stream-count=1 --stream-to=.../video2.raw`: exit `124`, 0-byte raw file.
- `v4l2-ctl --all` still reports both devices as `USU Camera 4K` UVC capture devices at `1280x720 YUYV`, 30 fps.

Interpretation: the current blocker is camera frame output/quality, not YOLO
model quality. Resolve the black/timeout frame issue before judging ball
detection or runtime 3D behavior.

## Last Snapshot

```json
{
  "generatedAtUnixMs": 1782681990920,
  "camera": {
    "state": "ready",
    "left": {
      "side": "left",
      "state": "ready",
      "code": "opened",
      "label": "Left USB camera opened",
      "detail": "1280x720 @ 60 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "6baa89dcf9826d6b6bde39d8700e754459200d678658fa93dcc8ef39d38d1d8a",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "opened",
      "label": "Right USB camera opened",
      "detail": "1280x720 @ 60 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "1e06335e308a62ca74e01506b3ae0f05cdf99c122bd88d1bcdaf5f740a72bf13",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "deviceCount": 2,
    "devices": [
      {
        "deviceId": "6baa89dcf9826d6b6bde39d8700e754459200d678658fa93dcc8ef39d38d1d8a",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      },
      {
        "deviceId": "1e06335e308a62ca74e01506b3ae0f05cdf99c122bd88d1bcdaf5f740a72bf13",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      }
    ]
  },
  "yoloArtifact": {
    "status": "loaded",
    "packagePath": "/artifacts/models/tennis_ball_yolo",
    "warnings": [],
    "selectedModel": "onnx",
    "modelPath": "model.onnx",
    "confidenceThreshold": 0.05
  },
  "calibrationArtifact": {
    "status": "loaded",
    "packagePath": "/artifacts/calibration/stereo_cam1_cam2",
    "warnings": [],
    "leftCameraId": "cam1",
    "rightCameraId": "cam2",
    "baselineMeters": 0.06778794228688073
  },
  "yoloLoopActive": true,
  "detections": {
    "left": {
      "side": "left",
      "state": "ready",
      "code": "updated",
      "label": "Left YOLO updated",
      "detail": "onnxruntime-web-yolo produced no tennis-ball detections for this frame.",
      "frameId": "left-1782681989413",
      "timestampUnixMs": 1782681989413,
      "imageSize": {
        "widthPx": 1280,
        "heightPx": 720
      },
      "detectionCount": 0,
      "warnings": [],
      "topConfidence": null,
      "centersPx": []
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "updated",
      "label": "Right YOLO updated",
      "detail": "onnxruntime-web-yolo produced no tennis-ball detections for this frame.",
      "frameId": "right-1782681989413",
      "timestampUnixMs": 1782681989413,
      "imageSize": {
        "widthPx": 1280,
        "heightPx": 720
      },
      "detectionCount": 0,
      "warnings": [],
      "topConfidence": null,
      "centersPx": []
    }
  },
  "runtime3d": {
    "code": "left-detections-missing",
    "state": "pending",
    "label": "Runtime 3D waiting for left detection",
    "detail": "Left YOLO updated: onnxruntime-web-yolo produced no tennis-ball detections for this frame.",
    "trailLength": 0,
    "selectedPairId": null,
    "latestPoint": null,
    "hasPrediction": false,
    "predictionSampleCount": 0,
    "landingPoint": null
  }
}
```
