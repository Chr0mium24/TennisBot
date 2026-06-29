import type { LandingPoint, TriangulatedBallPoint3D } from "../../../packages/contracts/src/index.js";
import type { StereoCalibrationArtifactLoadStatus, YoloArtifactLoadStatus } from "./artifacts";
import type { CameraRuntimeDevice, CameraRuntimeStatus, StereoCameraRuntimeStatus } from "./cameras";
import type { StereoYoloInferenceRuntimeStatus, YoloInferenceRuntimeStatus } from "./detections";
import type { Runtime3dState } from "./runtime-scene";

export type Live3dCameraRuntimeSnapshot = {
  state: StereoCameraRuntimeStatus["state"];
  left: CameraSideSnapshot;
  right: CameraSideSnapshot;
  deviceCount: number;
  devices: CameraRuntimeDevice[];
};

export type CameraSideSnapshot = Pick<
  CameraRuntimeStatus,
  "side" | "state" | "code" | "label" | "detail" | "deviceId" | "deviceLabel"
>;

export type YoloArtifactSnapshot = {
  status: YoloArtifactLoadStatus["status"];
  packagePath: string;
  warnings: string[];
  message?: string;
  errors?: string[];
  selectedModel?: string;
  modelPath?: string;
  confidenceThreshold?: number;
};

export type StereoCalibrationArtifactSnapshot = {
  status: StereoCalibrationArtifactLoadStatus["status"];
  packagePath: string;
  warnings: string[];
  message?: string;
  errors?: string[];
  leftCameraId?: string;
  rightCameraId?: string;
  baselineMeters?: number;
};

export type YoloInferenceSideSnapshot = Pick<
  YoloInferenceRuntimeStatus,
  | "side"
  | "state"
  | "code"
  | "label"
  | "detail"
  | "frameId"
  | "timestampUnixMs"
  | "imageSize"
  | "detectionCount"
  | "warnings"
> & {
  topConfidence: number | null;
  centersPx: Array<{ x: number; y: number }>;
};

export type Runtime3dSnapshot = {
  code: Runtime3dState["status"]["code"];
  state: Runtime3dState["status"]["state"];
  label: string;
  detail: string;
  trailLength: number;
  selectedPairId: string | null;
  latestPoint: TriangulatedBallPoint3D | null;
  hasPrediction: boolean;
  predictionSampleCount: number;
  landingPoint: LandingPoint | null;
};

export type RuntimeReadinessGate = {
  id:
    | "yolo-artifact"
    | "calibration-artifact"
    | "stereo-cameras"
    | "left-detection"
    | "right-detection"
    | "triangulation"
    | "prediction";
  label: string;
  state: "ready" | "pending" | "blocked";
  detail: string;
};

export type Live3dRuntimeSnapshot = {
  generatedAtUnixMs: number;
  camera: Live3dCameraRuntimeSnapshot;
  yoloArtifact: YoloArtifactSnapshot;
  calibrationArtifact: StereoCalibrationArtifactSnapshot;
  yoloLoopActive: boolean;
  detections: {
    left: YoloInferenceSideSnapshot;
    right: YoloInferenceSideSnapshot;
  };
  runtime3d: Runtime3dSnapshot;
  readinessGates: RuntimeReadinessGate[];
};

export function createLive3dRuntimeSnapshot(options: {
  generatedAtUnixMs: number;
  cameraStatus: StereoCameraRuntimeStatus;
  detectionStatus: StereoYoloInferenceRuntimeStatus;
  yoloStatus: YoloArtifactLoadStatus;
  calibrationStatus: StereoCalibrationArtifactLoadStatus;
  runtime3dState: Runtime3dState;
  yoloLoopActive: boolean;
}): Live3dRuntimeSnapshot {
  return {
    generatedAtUnixMs: options.generatedAtUnixMs,
    camera: cameraSnapshot(options.cameraStatus),
    yoloArtifact: yoloArtifactSnapshot(options.yoloStatus),
    calibrationArtifact: calibrationArtifactSnapshot(options.calibrationStatus),
    yoloLoopActive: options.yoloLoopActive,
    detections: {
      left: yoloInferenceSnapshot(options.detectionStatus.left),
      right: yoloInferenceSnapshot(options.detectionStatus.right),
    },
    runtime3d: runtime3dSnapshot(options.runtime3dState),
    readinessGates: createRuntimeReadinessGates(options),
  };
}

export function createRuntimeReadinessGates(options: {
  cameraStatus: StereoCameraRuntimeStatus;
  detectionStatus: StereoYoloInferenceRuntimeStatus;
  yoloStatus: YoloArtifactLoadStatus;
  calibrationStatus: StereoCalibrationArtifactLoadStatus;
  runtime3dState: Runtime3dState;
  yoloLoopActive: boolean;
}): RuntimeReadinessGate[] {
  return [
    {
      id: "yolo-artifact",
      label: "YOLO artifact",
      state: options.yoloStatus.status === "loaded" ? "ready" : "blocked",
      detail:
        options.yoloStatus.status === "loaded"
          ? `${options.yoloStatus.value.selectedModel} model loaded.`
          : options.yoloStatus.message,
    },
    {
      id: "calibration-artifact",
      label: "Calibration artifact",
      state: options.calibrationStatus.status === "loaded" ? "ready" : "blocked",
      detail:
        options.calibrationStatus.status === "loaded"
          ? `baseline ${options.calibrationStatus.value.extrinsics.baselineMeters?.toFixed(3) ?? "unknown"} m.`
          : options.calibrationStatus.message,
    },
    {
      id: "stereo-cameras",
      label: "Stereo cameras",
      state: cameraGateState(options.cameraStatus),
      detail:
        options.cameraStatus.state === "ready"
          ? `${options.cameraStatus.devices.length} browser video input(s).`
          : `${options.cameraStatus.left.detail} ${options.cameraStatus.right.detail}`,
    },
    detectionGate("left-detection", "Left detection", options.detectionStatus.left, options.yoloLoopActive),
    detectionGate("right-detection", "Right detection", options.detectionStatus.right, options.yoloLoopActive),
    {
      id: "triangulation",
      label: "Stereo 3D point",
      state:
        options.runtime3dState.latestPoint !== null
          ? "ready"
          : options.runtime3dState.status.code === "triangulation-blocked"
            ? "blocked"
            : "pending",
      detail: options.runtime3dState.latestPoint !== null ? "3D point available." : options.runtime3dState.status.detail,
    },
    {
      id: "prediction",
      label: "Prediction curve",
      state:
        options.runtime3dState.status.code === "prediction-ready"
          ? "ready"
          : options.runtime3dState.status.code === "prediction-blocked"
            ? "blocked"
            : "pending",
      detail:
        options.runtime3dState.status.code === "prediction-ready"
          ? `${options.runtime3dState.prediction?.samples.length ?? 0} prediction sample(s).`
          : options.runtime3dState.status.detail,
    },
  ];
}

function cameraGateState(status: StereoCameraRuntimeStatus): RuntimeReadinessGate["state"] {
  if (status.state === "ready" && status.devices.length >= 2) return "ready";
  if (status.state === "blocked") return "blocked";
  return "pending";
}

function detectionGate(
  id: "left-detection" | "right-detection",
  label: string,
  status: YoloInferenceRuntimeStatus,
  yoloLoopActive: boolean,
): RuntimeReadinessGate {
  if (status.detectionCount > 0) {
    return {
      id,
      label,
      state: "ready",
      detail: `${status.detectionCount} tennis-ball detection(s).`,
    };
  }
  return {
    id,
    label,
    state: status.state === "blocked" ? "blocked" : "pending",
    detail: yoloLoopActive ? status.detail : "YOLO loop is not running.",
  };
}

function cameraSnapshot(status: StereoCameraRuntimeStatus): Live3dCameraRuntimeSnapshot {
  return {
    state: status.state,
    left: status.left,
    right: status.right,
    deviceCount: status.devices.length,
    devices: status.devices,
  };
}

function yoloArtifactSnapshot(status: YoloArtifactLoadStatus): YoloArtifactSnapshot {
  if (status.status === "loaded") {
    return {
      status: status.status,
      packagePath: status.packagePath,
      warnings: status.warnings,
      selectedModel: status.value.selectedModel,
      modelPath: status.value.modelPath,
      confidenceThreshold: status.value.confidenceThreshold,
    };
  }

  return {
    status: status.status,
    packagePath: status.packagePath,
    warnings: status.warnings,
    message: status.message,
    errors: status.errors,
  };
}

function calibrationArtifactSnapshot(
  status: StereoCalibrationArtifactLoadStatus,
): StereoCalibrationArtifactSnapshot {
  if (status.status === "loaded") {
    return {
      status: status.status,
      packagePath: status.packagePath,
      warnings: status.warnings,
      leftCameraId: status.value.left.cameraId,
      rightCameraId: status.value.right.cameraId,
      baselineMeters: status.value.extrinsics.baselineMeters,
    };
  }

  return {
    status: status.status,
    packagePath: status.packagePath,
    warnings: status.warnings,
    message: status.message,
    errors: status.errors,
  };
}

function yoloInferenceSnapshot(status: YoloInferenceRuntimeStatus): YoloInferenceSideSnapshot {
  return {
    side: status.side,
    state: status.state,
    code: status.code,
    label: status.label,
    detail: status.detail,
    frameId: status.frameId,
    timestampUnixMs: status.timestampUnixMs,
    imageSize: status.imageSize,
    detectionCount: status.detectionCount,
    warnings: status.warnings,
    topConfidence:
      status.detections.length === 0
        ? null
        : Math.max(...status.detections.map((detection) => detection.confidence)),
    centersPx: status.detections.map((detection) => detection.centerPx),
  };
}

function runtime3dSnapshot(state: Runtime3dState): Runtime3dSnapshot {
  return {
    code: state.status.code,
    state: state.status.state,
    label: state.status.label,
    detail: state.status.detail,
    trailLength: state.trail.length,
    selectedPairId: state.selectedPair?.pairId ?? null,
    latestPoint: state.latestPoint,
    hasPrediction: state.prediction !== null,
    predictionSampleCount: state.prediction?.samples.length ?? 0,
    landingPoint: state.landingPoint,
  };
}
