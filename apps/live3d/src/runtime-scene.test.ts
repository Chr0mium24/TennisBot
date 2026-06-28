import { describe, expect, test } from "bun:test";
import type {
  Matrix3x4,
  StereoCalibration,
  Vector3,
  YoloDetection2D,
} from "../../../packages/contracts/src/index.js";
import { reprojectPoint } from "../../../packages/core/src/index.js";
import type { StereoCalibrationArtifactLoadStatus } from "./artifacts";
import type { YoloInferenceRuntimeStatus } from "./detections";
import {
  createInitialRuntime3dState,
  updateRuntime3dState,
} from "./runtime-scene";

const timestampUnixMs = 1_770_000_000_000;
const imageSize = { widthPx: 1280, heightPx: 720 };
const leftProjection: Matrix3x4 = {
  values: [1000, 0, 640, 0, 0, 1000, 360, 0, 0, 0, 1, 0],
  storage: "row-major",
};
const rightProjection: Matrix3x4 = {
  values: [1000, 0, 640, -200, 0, 1000, 360, 0, 0, 0, 1, 0],
  storage: "row-major",
};

describe("Live3D runtime 3D scene state", () => {
  test("selects a runtime stereo pair and triangulates with loaded calibration ids", () => {
    const state = updateRuntime3dState({
      previousState: createInitialRuntime3dState(),
      left: yoloStatus("left", [detectionFromPoint("left-runtime-camera", "left-a", point(0.1, 0.04, 2))]),
      right: yoloStatus("right", [
        detectionFromPoint("right-runtime-camera", "right-a", point(0.1, 0.04, 2)),
      ]),
      calibrationStatus: loadedCalibrationStatus(),
      frameId: "frame-1",
      timestampUnixMs,
    });

    expect(state.status.code).toBe("point-ready");
    expect(state.selectedPair?.left.cameraId).toBe("cal-left");
    expect(state.selectedPair?.right.cameraId).toBe("cal-right");
    expect(state.latestPoint?.positionMeters.x).toBeCloseTo(0.1, 10);
    expect(state.latestPoint?.positionMeters.y).toBeCloseTo(0.04, 10);
    expect(state.latestPoint?.positionMeters.z).toBeCloseTo(2, 10);
    expect(state.trail).toHaveLength(1);
    expect(state.prediction).toBeNull();
    expect(state.landingPoint).toBeNull();
  });

  test("builds a runtime prediction after two sequential triangulated points", () => {
    const first = updateRuntime3dState({
      previousState: createInitialRuntime3dState(),
      left: yoloStatus("left", [detectionFromPoint("browser-left", "left-1", point(0.1, 0.04, 2.2))]),
      right: yoloStatus("right", [detectionFromPoint("browser-right", "right-1", point(0.1, 0.04, 2.2))]),
      calibrationStatus: loadedCalibrationStatus(),
      frameId: "frame-1",
      timestampUnixMs,
    });
    const secondTimestampUnixMs = timestampUnixMs + 100;
    const second = updateRuntime3dState({
      previousState: first,
      left: yoloStatus("left", [
        detectionFromPoint("browser-left", "left-2", point(0.14, 0.03, 1.9), secondTimestampUnixMs),
      ]),
      right: yoloStatus("right", [
        detectionFromPoint("browser-right", "right-2", point(0.14, 0.03, 1.9), secondTimestampUnixMs),
      ]),
      calibrationStatus: loadedCalibrationStatus(),
      frameId: "frame-2",
      timestampUnixMs: secondTimestampUnixMs,
    });

    expect(second.status.code).toBe("prediction-ready");
    expect(second.trail).toHaveLength(2);
    expect(second.prediction?.samples).toHaveLength(9);
    expect(second.landingPoint?.surface).toBe("court");
    expect(second.landingPoint?.positionMeters.z).toBeCloseTo(0, 10);
  });

  test("returns a blocked status for missing calibration without throwing", () => {
    const state = updateRuntime3dState({
      previousState: createInitialRuntime3dState(),
      left: yoloStatus("left", [detectionFromPoint("browser-left", "left-1", point(0.1, 0.04, 2))]),
      right: yoloStatus("right", [detectionFromPoint("browser-right", "right-1", point(0.1, 0.04, 2))]),
      calibrationStatus: {
        status: "blocked",
        packagePath: "/artifacts/calibration/stereo_cam1_cam2",
        message: "Stereo calibration artifact package is blocked.",
        errors: ["cam1.json missing"],
        warnings: [],
      },
      frameId: "frame-1",
      timestampUnixMs,
    });

    expect(state.status.code).toBe("calibration-blocked");
    expect(state.latestPoint).toBeNull();
    expect(state.trail).toEqual([]);
  });

  test("reports no stereo pair when candidates fail epipolar pairing", () => {
    const state = updateRuntime3dState({
      previousState: createInitialRuntime3dState(),
      left: yoloStatus("left", [detection("browser-left", "left-1", 690, 380)]),
      right: yoloStatus("right", [detection("browser-right", "right-1", 590, 420)]),
      calibrationStatus: loadedCalibrationStatus(),
      frameId: "frame-1",
      timestampUnixMs,
    });

    expect(state.status.code).toBe("stereo-pair-missing");
    expect(state.pairing?.diagnostics.rejectedByEpipolarCount).toBe(1);
    expect(state.latestPoint).toBeNull();
  });
});

function loadedCalibrationStatus(): StereoCalibrationArtifactLoadStatus {
  return {
    status: "loaded",
    packagePath: "/artifacts/calibration/stereo_cam1_cam2",
    value: calibration(),
    warnings: [],
  };
}

function calibration(): StereoCalibration {
  return {
    left: {
      cameraId: "cal-left",
      imageSize,
      cameraMatrix: {
        values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
        storage: "row-major",
      },
      distortionModel: "none",
      distortionCoefficients: [],
    },
    right: {
      cameraId: "cal-right",
      imageSize,
      cameraMatrix: {
        values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
        storage: "row-major",
      },
      distortionModel: "none",
      distortionCoefficients: [],
    },
    extrinsics: {
      leftCameraId: "cal-left",
      rightCameraId: "cal-right",
      rotationLeftToRight: {
        values: [1, 0, 0, 0, 1, 0, 0, 0, 1],
        storage: "row-major",
      },
      translationLeftToRightMeters: { x: 0.2, y: 0, z: 0 },
      baselineMeters: 0.2,
    },
    rectifiedProjection: {
      leftCameraId: "cal-left",
      rightCameraId: "cal-right",
      leftProjectionMatrix: leftProjection,
      rightProjectionMatrix: rightProjection,
      imageSize,
      baselineMeters: 0.2,
    },
  };
}

function yoloStatus(
  side: "left" | "right",
  detections: YoloDetection2D[],
): YoloInferenceRuntimeStatus {
  return {
    side,
    state: "ready",
    code: "updated",
    label: `${side} updated`,
    detail: `${detections.length} synthetic detection(s).`,
    frameId: `${side}-frame`,
    timestampUnixMs,
    imageSize,
    detectionCount: detections.length,
    detections,
    warnings: [],
  };
}

function detectionFromPoint(
  cameraId: string,
  detectionId: string,
  positionMeters: Vector3,
  detectionTimestampUnixMs = timestampUnixMs,
): YoloDetection2D {
  const centerPx = reprojectPoint(
    cameraId.includes("right") ? rightProjection : leftProjection,
    positionMeters,
  );

  return detection(cameraId, detectionId, centerPx.x, centerPx.y, detectionTimestampUnixMs);
}

function detection(
  cameraId: string,
  detectionId: string,
  x: number,
  y: number,
  detectionTimestampUnixMs = timestampUnixMs,
): YoloDetection2D {
  return {
    detectionId,
    cameraId,
    frameId: `${cameraId}-frame`,
    timestampUnixMs: detectionTimestampUnixMs,
    classId: 0,
    label: "tennis_ball",
    confidence: 0.9,
    bboxPx: { xPx: x - 6, yPx: y - 6, widthPx: 12, heightPx: 12 },
    centerPx: { x, y },
  };
}

function point(x: number, y: number, z: number): Vector3 {
  return { x, y, z };
}
