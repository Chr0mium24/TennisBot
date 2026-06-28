# Live3D Hardware Loop Verification

- Started: 2026-06-28T21:45:01.660Z
- Finished: 2026-06-28T21:45:25.363Z
- App URL: http://localhost:5178
- Result: failed
- Error: Runtime 3D prediction did not reach ready.

## Steps

- passed: uvc controls - Applied brightness=64, gain=255, manual exposure=2047 to /dev/video0, /dev/video2.
- passed: app server - http://localhost:5178 is already serving Live3D.
- passed: chrome - /usr/bin/google-chrome is listening on CDP port 9233.
- passed: chrome tab - Opened http://localhost:5178.
- passed: page snapshot - window.__tennisbotLive3dSnapshot is available.
- passed: camera startup - 2 video input(s); left=USU Camera 4K: (a000:b111); right=USU Camera 4K: (a000:b111).
- failed: runtime 3D prediction - Left YOLO never produced a tennis-ball detection.
- passed: frame capture - Saved 2 video frame capture(s) under /home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_uvc_boost_frames.
- passed: frame quality - Captured frames are not near-black.

## Observations

- Snapshots seen: 16
- Max left detections: 0
- Max right detections: 0
- Max trail length: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing

## Frame Captures

- saved: left - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 69.29, non-black 100.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_uvc_boost_frames/left.png)
- saved: right - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 70.43, non-black 100.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_uvc_boost_frames/right.png)


## Last Snapshot

```json
{
  "generatedAtUnixMs": 1782683123423,
  "camera": {
    "state": "ready",
    "left": {
      "side": "left",
      "state": "ready",
      "code": "opened",
      "label": "Left USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "864ce5244b50eea730c017047fac3023139142766954f719bd335a122882d2d5",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "opened",
      "label": "Right USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "9d68f2a6f9576fe22046702402f013a2ba1f467c4efbde47da1cc08934fa122d",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "deviceCount": 2,
    "devices": [
      {
        "deviceId": "864ce5244b50eea730c017047fac3023139142766954f719bd335a122882d2d5",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      },
      {
        "deviceId": "9d68f2a6f9576fe22046702402f013a2ba1f467c4efbde47da1cc08934fa122d",
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
      "frameId": "left-1782683121903",
      "timestampUnixMs": 1782683121903,
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
      "frameId": "right-1782683121903",
      "timestampUnixMs": 1782683121903,
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
