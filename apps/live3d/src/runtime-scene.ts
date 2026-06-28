import type {
  LandingPoint,
  PredictionCurve,
  StereoPairingDiagnostics,
  TimestampedStereoDetectionPair,
  TriangulatedBallPoint3D,
  YoloDetection2D,
} from "../../../packages/contracts/src/index.js";
import {
  predictTrajectory,
  selectBestStereoPair,
  triangulateStereoPair,
  type SelectStereoPairResult,
} from "../../../packages/core/src/index.js";
import type { StereoCalibrationArtifactLoadStatus } from "./artifacts";
import type { YoloInferenceRuntimeStatus } from "./detections";

export type Runtime3dStatusState = "ready" | "pending" | "blocked";

export type Runtime3dStatusCode =
  | "idle"
  | "calibration-blocked"
  | "left-detections-missing"
  | "right-detections-missing"
  | "stereo-pair-missing"
  | "triangulation-blocked"
  | "point-ready"
  | "prediction-ready"
  | "prediction-blocked";

export type Runtime3dStatusItem = {
  code: Runtime3dStatusCode;
  state: Runtime3dStatusState;
  label: string;
  detail: string;
};

export type Runtime3dState = {
  status: Runtime3dStatusItem;
  pairing: SelectStereoPairResult | null;
  selectedPair: TimestampedStereoDetectionPair | null;
  latestPoint: TriangulatedBallPoint3D | null;
  trail: TriangulatedBallPoint3D[];
  prediction: PredictionCurve | null;
  landingPoint: LandingPoint | null;
};

export type UpdateRuntime3dStateOptions = {
  previousState: Runtime3dState;
  left: YoloInferenceRuntimeStatus;
  right: YoloInferenceRuntimeStatus;
  calibrationStatus: StereoCalibrationArtifactLoadStatus;
  frameId: string;
  timestampUnixMs: number;
  maxTimestampDeltaMs?: number;
  maxTrailPoints?: number;
};

const DEFAULT_MAX_TIMESTAMP_DELTA_MS = 33;
const DEFAULT_MAX_TRAIL_POINTS = 12;

export function createInitialRuntime3dState(): Runtime3dState {
  return {
    status: {
      code: "idle",
      state: "pending",
      label: "Runtime 3D idle",
      detail:
        "Runtime 3D waits for loaded calibration plus left and right YOLO detections.",
    },
    pairing: null,
    selectedPair: null,
    latestPoint: null,
    trail: [],
    prediction: null,
    landingPoint: null,
  };
}

export function updateRuntime3dState(options: UpdateRuntime3dStateOptions): Runtime3dState {
  if (options.calibrationStatus.status !== "loaded") {
    return preserveTrail(options.previousState, {
      status: {
        code: "calibration-blocked",
        state: "blocked",
        label: "Runtime 3D blocked by calibration",
        detail: options.calibrationStatus.message,
      },
      pairing: null,
      selectedPair: null,
      latestPoint: null,
      prediction: null,
      landingPoint: null,
    });
  }

  if (options.left.detections.length === 0) {
    return preserveTrail(options.previousState, {
      status: {
        code: "left-detections-missing",
        state: "pending",
        label: "Runtime 3D waiting for left detection",
        detail: leftOrRightDetail(options.left),
      },
      pairing: null,
      selectedPair: null,
      latestPoint: null,
      prediction: null,
      landingPoint: null,
    });
  }

  if (options.right.detections.length === 0) {
    return preserveTrail(options.previousState, {
      status: {
        code: "right-detections-missing",
        state: "pending",
        label: "Runtime 3D waiting for right detection",
        detail: leftOrRightDetail(options.right),
      },
      pairing: null,
      selectedPair: null,
      latestPoint: null,
      prediction: null,
      landingPoint: null,
    });
  }

  const calibration = options.calibrationStatus.value;
  const maxTimestampDeltaMs = options.maxTimestampDeltaMs ?? DEFAULT_MAX_TIMESTAMP_DELTA_MS;
  const leftDetections = withCameraId(options.left.detections, calibration.left.cameraId);
  const rightDetections = withCameraId(options.right.detections, calibration.right.cameraId);
  const pairing = selectBestStereoPair({
    pairId: `runtime-${options.frameId}`,
    timestampUnixMs: options.timestampUnixMs,
    maxTimestampDeltaMs,
    leftDetections,
    rightDetections,
    previousMatch: options.previousState.selectedPair,
    spec: {
      maxEpipolarErrorPx: 3,
      minDisparityPx: 1,
      maxDisparityPx: 300,
      temporalWeight: 0.25,
    },
  });

  if (pairing.match === null) {
    return preserveTrail(options.previousState, {
      status: {
        code: "stereo-pair-missing",
        state: "pending",
        label: "Runtime 3D has no stereo pair",
        detail: pairingDiagnosticsDetail(pairing.diagnostics),
      },
      pairing,
      selectedPair: null,
      latestPoint: null,
      prediction: null,
      landingPoint: null,
    });
  }

  const triangulation = triangulateStereoPair(calibration, pairing.match);
  if (triangulation.status !== "ok") {
    return preserveTrail(options.previousState, {
      status: {
        code: "triangulation-blocked",
        state: "blocked",
        label: "Runtime 3D triangulation failed",
        detail: triangulation.reason,
      },
      pairing,
      selectedPair: pairing.match,
      latestPoint: null,
      prediction: null,
      landingPoint: null,
    });
  }

  const trail = appendTrail(
    options.previousState.trail,
    triangulation.point,
    options.maxTrailPoints ?? DEFAULT_MAX_TRAIL_POINTS,
  );
  const prediction = predictTrajectory(trail, {
    generatedAtUnixMs: options.timestampUnixMs,
    gravityMetersPerSecondSquared: 9.81,
    horizonSec: 0.8,
    sampleCount: 9,
    landingSurfaceZMeters: 0,
    surface: "court",
  });

  if (prediction.status !== "ok") {
    const status =
      trail.length < 2
        ? {
            code: "point-ready" as const,
            state: "pending" as const,
            label: "Runtime 3D point ready",
            detail:
              "One runtime 3D point is ready; prediction waits for a second point with a later timestamp.",
          }
        : {
            code: "prediction-blocked" as const,
            state: "blocked" as const,
            label: "Runtime 3D prediction failed",
            detail: prediction.reason,
          };

    return {
      status,
      pairing,
      selectedPair: pairing.match,
      latestPoint: triangulation.point,
      trail,
      prediction: null,
      landingPoint: null,
    };
  }

  return {
    status: {
      code: "prediction-ready",
      state: "ready",
      label: "Runtime 3D prediction ready",
      detail:
        prediction.landingPoint === null
          ? `Runtime 3D trail has ${trail.length} point(s) and ${prediction.curve.samples.length} prediction samples; no court landing was found in the horizon.`
          : `Runtime 3D trail has ${trail.length} point(s), ${prediction.curve.samples.length} prediction samples, and one landing point.`,
    },
    pairing,
    selectedPair: pairing.match,
    latestPoint: triangulation.point,
    trail,
    prediction: prediction.curve,
    landingPoint: prediction.landingPoint,
  };
}

function preserveTrail(
  previousState: Runtime3dState,
  next: Omit<Runtime3dState, "trail">,
): Runtime3dState {
  return {
    ...next,
    trail: previousState.trail,
  };
}

function appendTrail(
  previousTrail: TriangulatedBallPoint3D[],
  point: TriangulatedBallPoint3D,
  maxTrailPoints: number,
): TriangulatedBallPoint3D[] {
  const withoutDuplicate = previousTrail.filter(
    (existing) => existing.pointId !== point.pointId,
  );
  return [...withoutDuplicate, point].slice(-maxTrailPoints);
}

function withCameraId(detections: YoloDetection2D[], cameraId: string): YoloDetection2D[] {
  return detections.map((detection) => ({
    ...detection,
    cameraId,
  }));
}

function leftOrRightDetail(status: YoloInferenceRuntimeStatus): string {
  return `${status.label}: ${status.detail}`;
}

function pairingDiagnosticsDetail(diagnostics: StereoPairingDiagnostics): string {
  return [
    `Evaluated ${diagnostics.evaluatedCandidateCount} candidate(s).`,
    `${diagnostics.rejectedByTimestampCount} rejected by timestamp.`,
    `${diagnostics.rejectedByEpipolarCount} rejected by epipolar error.`,
    `${diagnostics.rejectedByDisparityCount} rejected by disparity.`,
  ].join(" ");
}
