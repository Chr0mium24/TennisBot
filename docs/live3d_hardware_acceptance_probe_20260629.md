# Live3D Hardware Loop Verification

- Started: 2026-06-29T00:57:43.907Z
- Finished: 2026-06-29T00:58:02.110Z
- App URL: http://localhost:5178
- Result: failed
- Error: Runtime 3D prediction did not reach ready.

## Acceptance Checklist

- passed: Live3D app server - Started Live3D static server at http://localhost:5178. Evidence: step "app server" recorded passed.
- passed: Runtime snapshot export - window.__tennisbotLive3dSnapshot is available. Evidence: step "page snapshot" recorded passed.
- passed: YOLO artifact package - onnx model loaded from /artifacts/models/tennis_ball_yolo. Evidence: lastSnapshot.yoloArtifact.status is loaded.
- passed: Stereo calibration package - baseline=0.05248616443700974 m from /artifacts/calibration/stereo_cam1_cam2. Evidence: lastSnapshot.calibrationArtifact.status is loaded.
- passed: Stereo USB camera streams - 2 browser video input(s), left=USU Camera 4K: (a000:b111), right=USU Camera 4K: (a000:b111). Evidence: lastSnapshot.camera.state is ready.
- passed: Readable camera frames - Saved 2 non-black browser frame capture(s). Evidence: left max_luma=68.00, right max_luma=68.00.
- blocked: Left YOLO detection - The runtime was ready, but no tennis ball was visible to the detector. Evidence: artifact, camera, and frame-quality gates passed with maxDetections=0. Next: Put a visible tennis ball in both camera views or validate the model against the current lighting.
- blocked: Right YOLO detection - The runtime was ready, but no tennis ball was visible to the detector. Evidence: artifact, camera, and frame-quality gates passed with maxDetections=0. Next: Put a visible tennis ball in both camera views or validate the model against the current lighting.
- unknown: Stereo triangulated ball point - Triangulation is waiting on calibration plus left/right detections. Evidence: calibration=passed, left=blocked, right=blocked.
- unknown: Prediction curve and landing point - Prediction is waiting on stereo triangulation. Evidence: runtimeCodes=idle, left-detections-missing.

## Steps

- passed: uvc controls - Applied brightness=64, gain=255, manual exposure=2047 to /dev/video0, /dev/video2.
- passed: app server - Started Live3D static server at http://localhost:5178.
- passed: chrome - /usr/bin/google-chrome is listening on CDP port 9233.
- passed: chrome tab - Opened http://localhost:5178.
- passed: page snapshot - window.__tennisbotLive3dSnapshot is available.
- passed: camera startup - 2 video input(s); left=USU Camera 4K: (a000:b111); right=USU Camera 4K: (a000:b111).
- failed: runtime 3D prediction - Left YOLO never produced a tennis-ball detection.
- passed: frame capture - Saved 2 video frame capture(s) under /home/cr/Codes/TennisBot/docs/live3d_hardware_acceptance_probe_20260629_frames.
- passed: frame quality - Captured frames are not near-black.

## Observations

- Snapshots seen: 12
- Max left detections: 0
- Max right detections: 0
- Max trail length: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing

## Frame Captures

- saved: left - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 68.00, non-black 100.00%. (/home/cr/Codes/TennisBot/docs/live3d_hardware_acceptance_probe_20260629_frames/left.png)
- saved: right - 1280x720 PNG frame via image-capture; mean luma 68.00, max luma 68.00, non-black 100.00%. (/home/cr/Codes/TennisBot/docs/live3d_hardware_acceptance_probe_20260629_frames/right.png)


## Last Snapshot

```json
{
  "generatedAtUnixMs": 1782694680073,
  "camera": {
    "state": "ready",
    "left": {
      "side": "left",
      "state": "ready",
      "code": "opened",
      "label": "Left USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "e58779d28ee88665a08f71da1619c58be9889a1b3d1ac3839ba09a58b695164b",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "right": {
      "side": "right",
      "state": "ready",
      "code": "opened",
      "label": "Right USB camera opened",
      "detail": "1280x720 @ 30 fps requested from browser device USU Camera 4K: (a000:b111).",
      "deviceId": "daf6a0024472d7badbffbe737c7a410b18217d97d9596ba8bc9452d6ca4b5142",
      "deviceLabel": "USU Camera 4K: (a000:b111)"
    },
    "deviceCount": 2,
    "devices": [
      {
        "deviceId": "e58779d28ee88665a08f71da1619c58be9889a1b3d1ac3839ba09a58b695164b",
        "label": "USU Camera 4K: (a000:b111)",
        "kind": "videoinput"
      },
      {
        "deviceId": "daf6a0024472d7badbffbe737c7a410b18217d97d9596ba8bc9452d6ca4b5142",
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
    "baselineMeters": 0.05248616443700974
  },
  "yoloLoopActive": true,
  "detections": {
    "left": {
      "side": "left",
      "state": "ready",
      "code": "updated",
      "label": "Left YOLO updated",
      "detail": "onnxruntime-web-yolo produced no tennis-ball detections for this frame.",
      "frameId": "left-1782694678501",
      "timestampUnixMs": 1782694678501,
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
      "frameId": "right-1782694678501",
      "timestampUnixMs": 1782694678501,
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
