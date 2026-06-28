# Live3D Hardware Loop Verification

- Started: 2026-06-28T21:41:44.911Z
- Finished: 2026-06-28T21:42:08.400Z
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
- passed: frame capture - Saved 2 video frame capture(s) under /home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_boost_frames.
- passed: frame quality - Captured frames are not near-black.

## Observations

- Snapshots seen: 16
- Max left detections: 0
- Max right detections: 0
- Max trail length: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing

## Frame Captures

- saved: left - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 69.44, non-black 100.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_boost_frames/left.png)
- saved: right - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 68.00, non-black 100.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_boost_frames/right.png)


## Last Snapshot

```json
{
  "generatedAtUnixMs": 1782682926530,
  "camera": {
    "state": "ready",
    "left": {
      "side": "left",
      "state": "ready",
      "code": "opened",
      "label": "Left USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "db35321dca493aa78a943b49dd75b37f57dc1c7cb0ce2c1e830ed5976459a5e8",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "opened",
      "label": "Right USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "4f05e1f11c3bf01aca2220dab790a2be41062bf3ffeec73e7d5f172ecb51a73f",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "deviceCount": 2,
    "devices": [
      {
        "deviceId": "db35321dca493aa78a943b49dd75b37f57dc1c7cb0ce2c1e830ed5976459a5e8",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      },
      {
        "deviceId": "4f05e1f11c3bf01aca2220dab790a2be41062bf3ffeec73e7d5f172ecb51a73f",
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
      "frameId": "left-1782682925022",
      "timestampUnixMs": 1782682925022,
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
      "frameId": "right-1782682925022",
      "timestampUnixMs": 1782682925022,
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
