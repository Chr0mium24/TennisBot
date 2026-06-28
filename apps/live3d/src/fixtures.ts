import type {
  LandingPoint,
  PredictionCurve,
  RectifiedStereoProjectionMatrices,
  StereoCalibration,
  TimestampedStereoDetectionPair,
  TriangulatedBallPoint3D,
  YoloDetection2D,
} from "../../../packages/contracts/src/index.js";
import {
  reprojectPoint,
  selectBestStereoPair,
  triangulateStereoPair,
  predictTrajectory,
} from "../../../packages/core/src/index.js";
import type { SelectStereoPairResult } from "../../../packages/core/src/index.js";
import type { Live3dConfig } from "./config";

export type DetectionBox = {
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CameraFixture = {
  name: string;
  frameLabel: string;
  detections: YoloDetection2D[];
};

export type StatusState = "ready" | "pending" | "blocked" | "fixture";

export type RuntimeStatusItem = {
  label: string;
  state: StatusState;
  detail: string;
};

export type Point3d = {
  x: number;
  y: number;
  z: number;
};

export type SceneFixture = {
  ball: TriangulatedBallPoint3D;
  trail: TriangulatedBallPoint3D[];
  prediction: PredictionCurve;
  landing: LandingPoint;
};

export type Live3dFixture = {
  calibration: StereoCalibration;
  selectedPair: TimestampedStereoDetectionPair;
  stereoPairing: SelectStereoPairResult;
  cameras: {
    left: CameraFixture;
    right: CameraFixture;
  };
  scene: SceneFixture;
  status: RuntimeStatusItem[];
};

const FIXTURE_TIMESTAMP_UNIX_MS = 1_710_000_000_000;
const MAX_TIMESTAMP_DELTA_MS = 8;
const LEFT_CAMERA_ID = "fixture-left-camera";
const RIGHT_CAMERA_ID = "fixture-right-camera";
const IMAGE_WIDTH_PX = 1280;
const IMAGE_HEIGHT_PX = 720;

const rectifiedProjection: RectifiedStereoProjectionMatrices = {
  leftCameraId: LEFT_CAMERA_ID,
  rightCameraId: RIGHT_CAMERA_ID,
  leftProjectionMatrix: {
    values: [1000, 0, 640, 0, 0, 1000, 360, 0, 0, 0, 1, 0],
    storage: "row-major",
  },
  rightProjectionMatrix: {
    values: [1000, 0, 640, -200, 0, 1000, 360, 0, 0, 0, 1, 0],
    storage: "row-major",
  },
  imageSize: { widthPx: IMAGE_WIDTH_PX, heightPx: IMAGE_HEIGHT_PX },
  baselineMeters: 0.2,
};

export const fixtureStereoCalibration: StereoCalibration = {
  left: {
    cameraId: LEFT_CAMERA_ID,
    imageSize: { widthPx: IMAGE_WIDTH_PX, heightPx: IMAGE_HEIGHT_PX },
    cameraMatrix: {
      values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
      storage: "row-major",
    },
    distortionModel: "none",
    distortionCoefficients: [],
    sourceArtifactId: "fixture-stereo-calibration",
  },
  right: {
    cameraId: RIGHT_CAMERA_ID,
    imageSize: { widthPx: IMAGE_WIDTH_PX, heightPx: IMAGE_HEIGHT_PX },
    cameraMatrix: {
      values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
      storage: "row-major",
    },
    distortionModel: "none",
    distortionCoefficients: [],
    sourceArtifactId: "fixture-stereo-calibration",
  },
  extrinsics: {
    leftCameraId: LEFT_CAMERA_ID,
    rightCameraId: RIGHT_CAMERA_ID,
    rotationLeftToRight: {
      values: [1, 0, 0, 0, 1, 0, 0, 0, 1],
      storage: "row-major",
    },
    translationLeftToRightMeters: { x: 0.2, y: 0, z: 0 },
    baselineMeters: 0.2,
    sourceArtifactId: "fixture-stereo-calibration",
  },
  rectifiedProjection,
};

const fixturePointSeeds: Point3d[] = [
  { x: -0.18, y: 0.08, z: 2.85 },
  { x: -0.04, y: 0.06, z: 2.55 },
  { x: 0.1, y: 0.04, z: 2.25 },
];

export function createFixture(config: Live3dConfig): Live3dFixture {
  const coreFrames = buildFixtureCoreFrames();
  const latest = coreFrames.at(-1);

  if (latest === undefined) {
    throw new Error("Live3D fixture requires at least one stereo frame.");
  }

  const prediction = predictTrajectory(
    coreFrames.map((frame) => frame.point),
    {
      generatedAtUnixMs: latest.point.timestampUnixMs + 16,
      gravityMetersPerSecondSquared: 9.81,
      horizonSec: 0.8,
      sampleCount: 9,
      landingSurfaceZMeters: 0,
      surface: "court",
    },
  );

  if (prediction.status !== "ok" || prediction.landingPoint === null) {
    throw new Error(
      prediction.status === "ok"
        ? "Live3D fixture prediction did not produce a landing point."
        : prediction.reason,
    );
  }

  return {
    calibration: fixtureStereoCalibration,
    selectedPair: latest.pairing.match,
    stereoPairing: latest.pairing,
    cameras: {
      left: {
        name: config.cameras.left.label,
        frameLabel: config.cameras.left.devicePath,
        detections: [latest.pairing.match.left],
      },
      right: {
        name: config.cameras.right.label,
        frameLabel: config.cameras.right.devicePath,
        detections: [latest.pairing.match.right],
      },
    },
    scene: {
      ball: latest.point,
      trail: coreFrames.map((frame) => frame.point),
      prediction: prediction.curve,
      landing: prediction.landingPoint,
    },
    status: [
      {
        label: "Camera",
        state: "fixture",
        detail:
          "Fixture detections only; this does not validate USB cameras or live frame capture.",
      },
      {
        label: "Model",
        state: "pending",
        detail: `Expected package: ${config.artifacts.yoloModelPackagePath}. Fixture data does not validate real YOLO inference.`,
      },
      {
        label: "Calibration",
        state: "fixture",
        detail: `Using in-memory fixture projection matrices only; this does not validate real calibration package ${config.artifacts.stereoCalibrationPackagePath}.`,
      },
      {
        label: "Tracking",
        state: "fixture",
        detail:
          `Fixture pair selected by core stereo matching with disparity ${formatNumber(latest.pairing.match.disparityPx)} px; no real tracking validation.`,
      },
      {
        label: "Prediction",
        state: "fixture",
        detail:
          `Core projectile predictor generated ${prediction.curve.samples.length} fixture samples and one landing point; this does not validate real prediction.`,
      },
    ],
  };
}

export function detectionToBox(detection: YoloDetection2D): DetectionBox {
  return {
    label: detection.label,
    confidence: detection.confidence,
    x: (detection.bboxPx.xPx / IMAGE_WIDTH_PX) * 100,
    y: (detection.bboxPx.yPx / IMAGE_HEIGHT_PX) * 100,
    width: (detection.bboxPx.widthPx / IMAGE_WIDTH_PX) * 100,
    height: (detection.bboxPx.heightPx / IMAGE_HEIGHT_PX) * 100,
  };
}

type FixtureCoreFrame = {
  pairing: SelectStereoPairResult & { match: TimestampedStereoDetectionPair };
  point: TriangulatedBallPoint3D;
};

function buildFixtureCoreFrames(): FixtureCoreFrame[] {
  return fixturePointSeeds.map((positionMeters, index) => {
    const timestampUnixMs = FIXTURE_TIMESTAMP_UNIX_MS + index * 100;
    const leftDetection = makeDetectionFromPoint("left", index, timestampUnixMs, positionMeters);
    const rightDetection = makeDetectionFromPoint("right", index, timestampUnixMs + 2, positionMeters);
    const distractorRight = makeDetectionFromPoint("right-distractor", index, timestampUnixMs + 2, {
      ...positionMeters,
      x: positionMeters.x + 0.34,
    });
    const pairing = selectBestStereoPair({
      pairId: `fixture-pair-${index}`,
      timestampUnixMs,
      maxTimestampDeltaMs: MAX_TIMESTAMP_DELTA_MS,
      leftDetections: [leftDetection],
      rightDetections: [distractorRight, rightDetection],
      spec: {
        maxEpipolarErrorPx: 3,
        minDisparityPx: 20,
        maxDisparityPx: 140,
        temporalWeight: 0.25,
      },
    });

    if (pairing.match === null) {
      throw new Error("Live3D fixture stereo matcher did not select a pair.");
    }

    const triangulation = triangulateStereoPair(fixtureStereoCalibration, pairing.match);
    if (triangulation.status !== "ok") {
      throw new Error(triangulation.reason);
    }

    return {
      pairing: {
        ...pairing,
        match: pairing.match,
      },
      point: triangulation.point,
    };
  });
}

function makeDetectionFromPoint(
  side: "left" | "right" | "right-distractor",
  frameIndex: number,
  timestampUnixMs: number,
  positionMeters: Point3d,
): YoloDetection2D {
  const cameraId = side === "left" ? LEFT_CAMERA_ID : RIGHT_CAMERA_ID;
  const projection =
    side === "left"
      ? rectifiedProjection.leftProjectionMatrix
      : rectifiedProjection.rightProjectionMatrix;
  const centerPx = reprojectPoint(projection, positionMeters);
  const boxSizePx = 24 - frameIndex * 2;

  return {
    detectionId: `fixture-${side}-${frameIndex}`,
    cameraId,
    frameId: `fixture-${cameraId}-frame-${frameIndex}`,
    timestampUnixMs,
    classId: 0,
    label: "tennis_ball",
    confidence: side === "right-distractor" ? 0.72 : 0.9 - frameIndex * 0.02,
    bboxPx: {
      xPx: centerPx.x - boxSizePx / 2,
      yPx: centerPx.y - boxSizePx / 2,
      widthPx: boxSizePx,
      heightPx: boxSizePx,
    },
    centerPx,
  };
}

function formatNumber(value: number | undefined): string {
  return value === undefined ? "unknown" : value.toFixed(1);
}
