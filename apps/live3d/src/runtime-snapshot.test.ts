import { describe, expect, test } from "bun:test";
import type {
  StereoCalibration,
  TriangulatedBallPoint3D,
  YoloDetection2D,
} from "../../../packages/contracts/src/index.js";
import type {
  StereoCalibrationArtifactLoadStatus,
  YoloArtifactLoadStatus,
} from "./artifacts";
import type { StereoCameraRuntimeStatus } from "./cameras";
import type { StereoYoloInferenceRuntimeStatus } from "./detections";
import type { Runtime3dState } from "./runtime-scene";
import { createLive3dRuntimeSnapshot } from "./runtime-snapshot";

describe("Live3D runtime snapshot", () => {
  test("summarizes loaded artifacts, detections, and runtime 3D state", () => {
    const snapshot = createLive3dRuntimeSnapshot({
      generatedAtUnixMs: 1_777_000_000_000,
      cameraStatus: readyCameraStatus(),
      detectionStatus: detectionStatus(),
      yoloStatus: loadedYoloStatus(),
      calibrationStatus: loadedCalibrationStatus(),
      runtime3dState: predictionReadyState(),
      yoloLoopActive: true,
    });

    expect(snapshot.yoloArtifact.status).toBe("loaded");
    expect(snapshot.yoloArtifact.selectedModel).toBe("onnx");
    expect(snapshot.calibrationArtifact.baselineMeters).toBe(0.2);
    expect(snapshot.detections.left.detectionCount).toBe(1);
    expect(snapshot.detections.left.topConfidence).toBe(0.91);
    expect(snapshot.runtime3d.code).toBe("prediction-ready");
    expect(snapshot.runtime3d.trailLength).toBe(2);
    expect(snapshot.runtime3d.predictionSampleCount).toBe(2);
    expect(snapshot.runtime3d.landingPoint?.surface).toBe("court");
    expect(snapshot.readinessGates.map((gate) => gate.state)).toEqual([
      "ready",
      "ready",
      "ready",
      "ready",
      "ready",
      "ready",
      "ready",
    ]);
    expect(snapshot.readinessGates.find((gate) => gate.id === "prediction")?.detail).toBe("2 prediction sample(s).");
  });

  test("preserves blocked artifact errors for headless diagnostics", () => {
    const snapshot = createLive3dRuntimeSnapshot({
      generatedAtUnixMs: 1_777_000_000_000,
      cameraStatus: pendingCameraStatus(),
      detectionStatus: detectionStatus(),
      yoloStatus: {
        status: "blocked",
        packagePath: "/artifacts/models/tennis_ball_yolo",
        message: "YOLO artifact validation failed.",
        errors: ["model.onnx missing"],
        warnings: [],
      },
      calibrationStatus: {
        status: "blocked",
        packagePath: "/artifacts/calibration/stereo_cam1_cam2",
        message: "Stereo calibration artifact validation failed.",
        errors: ["rectification.json missing"],
        warnings: ["verification.json missing"],
      },
      runtime3dState: idleRuntime3dState(),
      yoloLoopActive: false,
    });

    expect(snapshot.yoloArtifact.errors).toContain("model.onnx missing");
    expect(snapshot.calibrationArtifact.errors).toContain("rectification.json missing");
    expect(snapshot.calibrationArtifact.warnings).toContain("verification.json missing");
    expect(snapshot.runtime3d.code).toBe("idle");
    expect(snapshot.readinessGates.find((gate) => gate.id === "yolo-artifact")?.state).toBe("blocked");
    expect(snapshot.readinessGates.find((gate) => gate.id === "prediction")?.state).toBe("pending");
  });

  test("keeps detection and prediction gates pending before visible ball detections", () => {
    const snapshot = createLive3dRuntimeSnapshot({
      generatedAtUnixMs: 1_777_000_000_000,
      cameraStatus: readyCameraStatus(),
      detectionStatus: {
        left: { ...detectionStatus().left, detections: [], detectionCount: 0, detail: "No left tennis ball." },
        right: { ...detectionStatus().right, detections: [], detectionCount: 0, detail: "No right tennis ball." },
      },
      yoloStatus: loadedYoloStatus(),
      calibrationStatus: loadedCalibrationStatus(),
      runtime3dState: idleRuntime3dState(),
      yoloLoopActive: true,
    });

    expect(snapshot.readinessGates.find((gate) => gate.id === "stereo-cameras")?.state).toBe("ready");
    expect(snapshot.readinessGates.find((gate) => gate.id === "left-detection")?.detail).toBe("No left tennis ball.");
    expect(snapshot.readinessGates.find((gate) => gate.id === "prediction")?.state).toBe("pending");
  });
});

function pendingCameraStatus(): StereoCameraRuntimeStatus {
  return {
    state: "pending",
    left: {
      side: "left",
      state: "pending",
      code: "not-started",
      label: "Left camera idle",
      detail: "Camera has not started.",
    },
    right: {
      side: "right",
      state: "pending",
      code: "not-started",
      label: "Right camera idle",
      detail: "Camera has not started.",
    },
    devices: [
      { deviceId: "left-device", label: "Left USB", kind: "videoinput" },
      { deviceId: "right-device", label: "Right USB", kind: "videoinput" },
    ],
  };
}

function readyCameraStatus(): StereoCameraRuntimeStatus {
  const pending = pendingCameraStatus();
  return {
    ...pending,
    state: "ready",
    left: {
      ...pending.left,
      state: "ready",
      code: "opened",
      label: "Left USB camera opened",
      detail: "Left camera opened.",
    },
    right: {
      ...pending.right,
      state: "ready",
      code: "opened",
      label: "Right USB camera opened",
      detail: "Right camera opened.",
    },
    streams: {
      left: {} as MediaStream,
      right: {} as MediaStream,
    },
  };
}

function loadedYoloStatus(): YoloArtifactLoadStatus {
  return {
    status: "loaded",
    packagePath: "/artifacts/models/tennis_ball_yolo",
    value: {
      packageName: "tennis_ball_yolo",
      packageVersion: "0.1.0",
      contractVersion: "0.1.0",
      labels: ["tennis_ball"],
      inputSizePx: { widthPx: 1280, heightPx: 1280 },
      inputColor: "RGB",
      boxFormat: "xyxy_pixels",
      confidenceThreshold: 0.05,
      classId: 0,
      modelPath: "model.onnx",
      modelRuntime: "onnxruntime",
      selectedModel: "onnx",
      modelChecks: [],
    },
    warnings: [],
  };
}

function loadedCalibrationStatus(): StereoCalibrationArtifactLoadStatus {
  return {
    status: "loaded",
    packagePath: "/artifacts/calibration/stereo_cam1_cam2",
    value: calibration(),
    warnings: ["runtime quality warning"],
  };
}

function calibration(): StereoCalibration {
  return {
    left: {
      cameraId: "cam1",
      imageSize: { widthPx: 1280, heightPx: 720 },
      cameraMatrix: {
        values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
        storage: "row-major",
      },
      distortionModel: "none",
      distortionCoefficients: [],
    },
    right: {
      cameraId: "cam2",
      imageSize: { widthPx: 1280, heightPx: 720 },
      cameraMatrix: {
        values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
        storage: "row-major",
      },
      distortionModel: "none",
      distortionCoefficients: [],
    },
    extrinsics: {
      leftCameraId: "cam1",
      rightCameraId: "cam2",
      rotationLeftToRight: {
        values: [1, 0, 0, 0, 1, 0, 0, 0, 1],
        storage: "row-major",
      },
      translationLeftToRightMeters: { x: 0.2, y: 0, z: 0 },
      baselineMeters: 0.2,
    },
  };
}

function detectionStatus(): StereoYoloInferenceRuntimeStatus {
  return {
    left: {
      side: "left",
      state: "ready",
      code: "updated",
      label: "Left YOLO updated",
      detail: "One detection.",
      frameId: "left-1",
      timestampUnixMs: 1_777_000_000_000,
      imageSize: { widthPx: 1280, heightPx: 720 },
      detectionCount: 1,
      detections: [detection("left")],
      warnings: [],
    },
    right: {
      side: "right",
      state: "ready",
      code: "updated",
      label: "Right YOLO updated",
      detail: "One detection.",
      frameId: "right-1",
      timestampUnixMs: 1_777_000_000_000,
      imageSize: { widthPx: 1280, heightPx: 720 },
      detectionCount: 1,
      detections: [detection("right")],
      warnings: [],
    },
  };
}

function detection(side: "left" | "right"): YoloDetection2D {
  return {
    detectionId: `${side}-detection`,
    cameraId: side,
    frameId: `${side}-1`,
    timestampUnixMs: 1_777_000_000_000,
    classId: 0,
    label: "tennis_ball",
    confidence: side === "left" ? 0.91 : 0.86,
    bboxPx: { xPx: 600, yPx: 300, widthPx: 40, heightPx: 42 },
    centerPx: { x: 620, y: 321 },
  };
}

function predictionReadyState(): Runtime3dState {
  const first = point("point-1", 1_777_000_000_000, 1.2);
  const second = point("point-2", 1_777_000_000_100, 1.1);
  return {
    status: {
      code: "prediction-ready",
      state: "ready",
      label: "Runtime 3D prediction ready",
      detail: "Runtime 3D trail has 2 point(s), 2 prediction samples, and one landing point.",
    },
    pairing: null,
    selectedPair: null,
    latestPoint: second,
    trail: [first, second],
    prediction: {
      predictionId: "prediction-1",
      generatedAtUnixMs: 1_777_000_000_100,
      sourcePointIds: ["point-1", "point-2"],
      model: "projectile-3d-constant-gravity",
      quality: "medium",
      samples: [
        {
          tOffsetSec: 0,
          positionMeters: second.positionMeters,
          velocityMetersPerSec: { x: 0, y: 0, z: -1 },
        },
        {
          tOffsetSec: 0.2,
          positionMeters: { x: 0, y: 1, z: 0.7 },
          velocityMetersPerSec: { x: 0, y: 0, z: -2.96 },
        },
      ],
    },
    landingPoint: {
      landingId: "landing-1",
      generatedAtUnixMs: 1_777_000_000_100,
      positionMeters: { x: 0, y: 1.4, z: 0 },
      tOffsetSec: 0.4,
      confidence: 0.7,
      surface: "court",
      sourcePredictionId: "prediction-1",
    },
  };
}

function idleRuntime3dState(): Runtime3dState {
  return {
    status: {
      code: "idle",
      state: "pending",
      label: "Runtime 3D idle",
      detail: "Waiting.",
    },
    pairing: null,
    selectedPair: null,
    latestPoint: null,
    trail: [],
    prediction: null,
    landingPoint: null,
  };
}

function point(
  pointId: string,
  timestampUnixMs: number,
  zMeters: number,
): TriangulatedBallPoint3D {
  return {
    pointId,
    timestampUnixMs,
    positionMeters: { x: 0, y: 1, z: zMeters },
    sourcePairId: "pair-1",
    reprojectionErrorPx: 0.3,
  };
}
