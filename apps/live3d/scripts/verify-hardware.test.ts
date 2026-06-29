import { describe, expect, test } from "bun:test";

import {
  createAcceptanceChecklist,
  renderReport,
  type VerificationResult,
} from "./verify-hardware";
import type { Runtime3dSnapshot } from "../src/runtime-snapshot";

describe("Live3D hardware verification report", () => {
  test("classifies no-ball scenes as blocked after the runtime prerequisites pass", () => {
    const result = verificationResult({
      maxLeftDetections: 0,
      maxRightDetections: 0,
      maxTrailLength: 0,
      maxPredictionSamples: 0,
      runtimeCodes: ["idle", "left-detections-missing"],
      runtimeCode: "left-detections-missing",
      status: "failed",
      error: "Runtime 3D prediction did not reach ready.",
    });

    const gates = createAcceptanceChecklist(result);
    expect(gates.find((gate) => gate.id === "yolo-artifact")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "calibration-artifact")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "stereo-camera-streams")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "frame-quality")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "left-yolo-detection")?.status).toBe("blocked");
    expect(gates.find((gate) => gate.id === "right-yolo-detection")?.status).toBe("blocked");
    expect(gates.find((gate) => gate.id === "trajectory-prediction")?.status).toBe("unknown");

    const report = renderReport(result);
    expect(report).toContain("## Acceptance Checklist");
    expect(report).toContain("blocked: Left YOLO detection");
    expect(report).toContain("Put a visible tennis ball in both camera views");
  });

  test("marks the prediction gate passed when runtime reaches prediction-ready", () => {
    const result = verificationResult({
      maxLeftDetections: 1,
      maxRightDetections: 1,
      maxTrailLength: 2,
      maxPredictionSamples: 12,
      runtimeCodes: ["idle", "prediction-ready"],
      runtimeCode: "prediction-ready",
      status: "passed",
    });

    const gates = createAcceptanceChecklist(result);
    expect(gates.find((gate) => gate.id === "left-yolo-detection")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "right-yolo-detection")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "stereo-triangulation")?.status).toBe("passed");
    expect(gates.find((gate) => gate.id === "trajectory-prediction")?.status).toBe("passed");
  });
});

function verificationResult(options: {
  maxLeftDetections: number;
  maxRightDetections: number;
  maxTrailLength: number;
  maxPredictionSamples: number;
  runtimeCodes: string[];
  runtimeCode: Runtime3dSnapshot["code"];
  status: "passed" | "failed";
  error?: string;
}): VerificationResult {
  return {
    status: options.status,
    startedAt: new Date("2026-06-29T00:00:00.000Z"),
    finishedAt: new Date("2026-06-29T00:00:05.000Z"),
    appUrl: "http://localhost:5178",
    steps: [
      {
        name: "app server",
        status: "passed",
        detail: "http://localhost:5178 is already serving Live3D.",
      },
      {
        name: "page snapshot",
        status: "passed",
        detail: "window.__tennisbotLive3dSnapshot is available.",
      },
      {
        name: "camera startup",
        status: "passed",
        detail: "2 video input(s); left=Left USB; right=Right USB.",
      },
    ],
    observation: {
      snapshotsSeen: 4,
      maxLeftDetections: options.maxLeftDetections,
      maxRightDetections: options.maxRightDetections,
      maxTrailLength: options.maxTrailLength,
      maxPredictionSamples: options.maxPredictionSamples,
      runtimeCodes: options.runtimeCodes,
      lastSnapshot: {
        generatedAtUnixMs: 1_782_662_400_000,
        camera: {
          state: "ready",
          left: {
            side: "left",
            state: "ready",
            code: "opened",
            label: "Left USB camera opened",
            detail: "Left camera opened.",
            deviceId: "left-device",
            deviceLabel: "Left USB",
          },
          right: {
            side: "right",
            state: "ready",
            code: "opened",
            label: "Right USB camera opened",
            detail: "Right camera opened.",
            deviceId: "right-device",
            deviceLabel: "Right USB",
          },
          deviceCount: 2,
          devices: [],
        },
        yoloArtifact: {
          status: "loaded",
          packagePath: "/artifacts/models/tennis_ball_yolo",
          warnings: [],
          selectedModel: "onnx",
          modelPath: "model.onnx",
          confidenceThreshold: 0.05,
        },
        calibrationArtifact: {
          status: "loaded",
          packagePath: "/artifacts/calibration/stereo_cam1_cam2",
          warnings: [],
          leftCameraId: "cam1",
          rightCameraId: "cam2",
          baselineMeters: 0.052486,
        },
        yoloLoopActive: true,
        detections: {
          left: {
            side: "left",
            state: "ready",
            code: "updated",
            label: "Left YOLO updated",
            detail: "Left detection state.",
            frameId: "left-1",
            timestampUnixMs: 1_782_662_400_000,
            imageSize: { widthPx: 1280, heightPx: 720 },
            detectionCount: options.maxLeftDetections,
            warnings: [],
            topConfidence: options.maxLeftDetections > 0 ? 0.9 : null,
            centersPx: options.maxLeftDetections > 0 ? [{ x: 640, y: 360 }] : [],
          },
          right: {
            side: "right",
            state: "ready",
            code: "updated",
            label: "Right YOLO updated",
            detail: "Right detection state.",
            frameId: "right-1",
            timestampUnixMs: 1_782_662_400_000,
            imageSize: { widthPx: 1280, heightPx: 720 },
            detectionCount: options.maxRightDetections,
            warnings: [],
            topConfidence: options.maxRightDetections > 0 ? 0.88 : null,
            centersPx: options.maxRightDetections > 0 ? [{ x: 620, y: 360 }] : [],
          },
        },
        runtime3d: {
          code: options.runtimeCode,
          state: options.status === "passed" ? "ready" : "pending",
          label: "Runtime 3D status",
          detail: "Runtime 3D detail.",
          trailLength: options.maxTrailLength,
          selectedPairId: options.maxTrailLength > 0 ? "pair-1" : null,
          latestPoint: null,
          hasPrediction: options.maxPredictionSamples > 0,
          predictionSampleCount: options.maxPredictionSamples,
          landingPoint: null,
        },
      },
    },
    captures: [
      {
        label: "left",
        status: "saved",
        detail: "1280x720 PNG frame; mean luma 68.0, max luma 69.0.",
        maxLuma: 69,
        meanLuma: 68,
        nonBlackPixelPercent: 100,
      },
      {
        label: "right",
        status: "saved",
        detail: "1280x720 PNG frame; mean luma 67.0, max luma 68.0.",
        maxLuma: 68,
        meanLuma: 67,
        nonBlackPixelPercent: 100,
      },
    ],
    error: options.error,
  };
}
