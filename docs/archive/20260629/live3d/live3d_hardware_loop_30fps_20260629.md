# Live3D Hardware Loop Verification

- Started: 2026-06-28T21:39:16.675Z
- Finished: 2026-06-28T21:39:40.280Z
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
- passed: frame capture - Saved 2 video frame capture(s) under /home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_frames.
- failed: frame quality - left, right capture(s) are near-black; check camera exposure, lens cover, or browser capture backend before judging YOLO.

## Observations

- Snapshots seen: 16
- Max left detections: 0
- Max right detections: 0
- Max trail length: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing

## Frame Captures

- saved: left - 1280x720 PNG frame via image-capture; mean luma 0.00, max luma 0.64, non-black 0.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_frames/left.png)
- saved: right - 1280x720 PNG frame via image-capture; mean luma 0.00, max luma 0.29, non-black 0.00%. (/home/cr/Codes/TennisBot/artifacts/hardware_smoke/20260629/live3d_hardware_loop_30fps_frames/right.png)


## Last Snapshot

```json
{
  "generatedAtUnixMs": 1782682778424,
  "camera": {
    "state": "ready",
    "left": {
      "side": "left",
      "state": "ready",
      "code": "opened",
      "label": "Left USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "512b2cedbe039e38b70ca38cdf1483cdfac412a7540233e719ed61fd2e6e3c88",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "opened",
      "label": "Right USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "78a1253bad4bdf16dbebaac77a401a0e3b11a27b20ca4a4822f9022f5d36319d",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "deviceCount": 2,
    "devices": [
      {
        "deviceId": "512b2cedbe039e38b70ca38cdf1483cdfac412a7540233e719ed61fd2e6e3c88",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      },
      {
        "deviceId": "78a1253bad4bdf16dbebaac77a401a0e3b11a27b20ca4a4822f9022f5d36319d",
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
      "frameId": "left-1782682776919",
      "timestampUnixMs": 1782682776919,
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
      "frameId": "right-1782682776919",
      "timestampUnixMs": 1782682776919,
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
