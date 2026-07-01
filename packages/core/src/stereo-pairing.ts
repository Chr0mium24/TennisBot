import type {
  StereoPairingDiagnostics,
  StereoCalibration,
  TimestampedStereoDetectionPair,
  TriangulatedBallPoint3D,
  Vector2,
  Vector3,
  YoloDetection2D,
} from '../../contracts/src/index.js';
import {
  disparityPx,
  epipolarErrorRectified,
  rectifiedDisparityPx,
  rectifyImagePoint,
  triangulateStereoPair,
} from './projection.js';

export interface StereoPairingSpec {
  maxEpipolarErrorPx: number;
  minDisparityPx: number;
  maxDisparityPx: number;
  temporalWeight: number;
  maxDepthMeters: number;
  maxReprojectionErrorPx: number;
  reprojectionWeight: number;
  temporal3dWeight: number;
}

export interface SelectStereoPairOptions {
  pairId: string;
  timestampUnixMs: number;
  maxTimestampDeltaMs: number;
  leftDetections: YoloDetection2D[];
  rightDetections: YoloDetection2D[];
  previousMatch?: TimestampedStereoDetectionPair | null;
  previousPoint?: TriangulatedBallPoint3D | Vector3 | null;
  calibration?: StereoCalibration;
  spec?: Partial<StereoPairingSpec>;
}

export interface SelectStereoPairResult {
  match: TimestampedStereoDetectionPair | null;
  diagnostics: StereoPairingDiagnostics;
}

const DEFAULT_SPEC: StereoPairingSpec = {
  maxEpipolarErrorPx: 3,
  minDisparityPx: 1,
  maxDisparityPx: 300,
  temporalWeight: 0.25,
  maxDepthMeters: Number.POSITIVE_INFINITY,
  maxReprojectionErrorPx: Number.POSITIVE_INFINITY,
  reprojectionWeight: 0.25,
  temporal3dWeight: 0.02,
};

export function selectBestStereoPair(options: SelectStereoPairOptions): SelectStereoPairResult {
  const spec = { ...DEFAULT_SPEC, ...options.spec };
  let bestMatch: TimestampedStereoDetectionPair | null = null;
  let bestCost = Number.POSITIVE_INFINITY;
  let evaluatedCandidateCount = 0;
  let rejectedByTimestampCount = 0;
  let rejectedByEpipolarCount = 0;
  let rejectedByDisparityCount = 0;
  let rejectedByTriangulationCount = 0;
  let rejectedByDepthCount = 0;
  let rejectedByReprojectionCount = 0;
  const previousPoint = options.previousPoint === undefined || options.previousPoint === null
    ? null
    : pointPosition(options.previousPoint);

  for (const left of options.leftDetections) {
    for (const right of options.rightDetections) {
      evaluatedCandidateCount += 1;
      const timestampDeltaMs = Math.abs(left.timestampUnixMs - right.timestampUnixMs);
      if (timestampDeltaMs > options.maxTimestampDeltaMs) {
        rejectedByTimestampCount += 1;
        continue;
      }

      const candidatePoints = stereoCandidatePoints(left, right, options.calibration);
      const epipolarErrorPx = epipolarErrorRectified(candidatePoints.leftPx, candidatePoints.rightPx);
      if (epipolarErrorPx > spec.maxEpipolarErrorPx) {
        rejectedByEpipolarCount += 1;
        continue;
      }

      const disparity = options.calibration?.rectifiedProjection === undefined
        ? disparityPx(candidatePoints.leftPx, candidatePoints.rightPx)
        : rectifiedDisparityPx(options.calibration.rectifiedProjection, candidatePoints.leftPx, candidatePoints.rightPx);
      if (disparity < spec.minDisparityPx || disparity > spec.maxDisparityPx) {
        rejectedByDisparityCount += 1;
        continue;
      }

      let triangulatedPoint: TriangulatedBallPoint3D | null = null;
      let reprojectionErrorPx = 0;
      if (options.calibration?.rectifiedProjection !== undefined) {
        const triangulation = triangulateStereoPair(options.calibration, candidatePair({
          pairId: options.pairId,
          timestampUnixMs: options.timestampUnixMs,
          maxTimestampDeltaMs: options.maxTimestampDeltaMs,
          left,
          right,
          leftRectifiedCenterPx: candidatePoints.leftPx,
          rightRectifiedCenterPx: candidatePoints.rightPx,
          disparityPx: disparity,
          epipolarErrorPx,
        }));
        if (triangulation.status !== 'ok') {
          rejectedByTriangulationCount += 1;
          continue;
        }

        triangulatedPoint = triangulation.point;
        const zMeters = triangulatedPoint.positionMeters.z;
        if (!Number.isFinite(zMeters) || zMeters <= 0 || zMeters > spec.maxDepthMeters) {
          rejectedByDepthCount += 1;
          continue;
        }

        reprojectionErrorPx = triangulatedPoint.diagnostics?.averageReprojectionErrorPx ?? 0;
        if (reprojectionErrorPx > spec.maxReprojectionErrorPx) {
          rejectedByReprojectionCount += 1;
          continue;
        }
      }

      const confidence = options.calibration?.rectifiedProjection === undefined
        ? 0.5 * (left.confidence + right.confidence)
        : Math.min(left.confidence, right.confidence);
      let cost = epipolarErrorPx + spec.reprojectionWeight * reprojectionErrorPx - confidence;
      if (previousPoint !== null && triangulatedPoint !== null) {
        cost += spec.temporal3dWeight * distance3d(triangulatedPoint.positionMeters, previousPoint);
      } else if (options.previousMatch !== undefined && options.previousMatch !== null) {
        cost += spec.temporalWeight * temporalDistance(left, right, options.previousMatch);
      }

      if (cost >= bestCost) {
        continue;
      }

      bestCost = cost;
      bestMatch = {
        pairId: options.pairId,
        timestampUnixMs: options.timestampUnixMs,
        left,
        right,
        maxTimestampDeltaMs: options.maxTimestampDeltaMs,
        leftRectifiedCenterPx: candidatePoints.isRectified ? candidatePoints.leftPx : undefined,
        rightRectifiedCenterPx: candidatePoints.isRectified ? candidatePoints.rightPx : undefined,
        matchConfidence: clamp01(confidence),
        disparityPx: disparity,
        epipolarErrorPx,
        matchCost: cost,
      };
    }
  }

  return {
    match: bestMatch,
    diagnostics: {
      evaluatedCandidateCount,
      rejectedByTimestampCount,
      rejectedByEpipolarCount,
      rejectedByDisparityCount,
      rejectedByTriangulationCount,
      rejectedByDepthCount,
      rejectedByReprojectionCount,
      bestCost: Number.isFinite(bestCost) ? bestCost : null,
    },
  };
}

function stereoCandidatePoints(
  left: YoloDetection2D,
  right: YoloDetection2D,
  calibration: StereoCalibration | undefined,
): { leftPx: Vector2; rightPx: Vector2; isRectified: boolean } {
  const projections = calibration?.rectifiedProjection;
  if (
    calibration === undefined ||
    projections?.leftRectificationMatrix === undefined ||
    projections.rightRectificationMatrix === undefined
  ) {
    return { leftPx: left.centerPx, rightPx: right.centerPx, isRectified: false };
  }

  return {
    leftPx: rectifyImagePoint(
      calibration.left,
      projections.leftRectificationMatrix,
      projections.leftProjectionMatrix,
      left.centerPx,
    ),
    rightPx: rectifyImagePoint(
      calibration.right,
      projections.rightRectificationMatrix,
      projections.rightProjectionMatrix,
      right.centerPx,
    ),
    isRectified: true,
  };
}

function candidatePair(options: {
  pairId: string;
  timestampUnixMs: number;
  maxTimestampDeltaMs: number;
  left: YoloDetection2D;
  right: YoloDetection2D;
  leftRectifiedCenterPx: Vector2;
  rightRectifiedCenterPx: Vector2;
  disparityPx: number;
  epipolarErrorPx: number;
}): TimestampedStereoDetectionPair {
  return {
    pairId: options.pairId,
    timestampUnixMs: options.timestampUnixMs,
    left: options.left,
    right: options.right,
    maxTimestampDeltaMs: options.maxTimestampDeltaMs,
    leftRectifiedCenterPx: options.leftRectifiedCenterPx,
    rightRectifiedCenterPx: options.rightRectifiedCenterPx,
    matchConfidence: clamp01(Math.min(options.left.confidence, options.right.confidence)),
    disparityPx: options.disparityPx,
    epipolarErrorPx: options.epipolarErrorPx,
  };
}

function temporalDistance(
  left: YoloDetection2D,
  right: YoloDetection2D,
  previousMatch: TimestampedStereoDetectionPair,
): number {
  return Math.hypot(
    left.centerPx.x - previousMatch.left.centerPx.x,
    left.centerPx.y - previousMatch.left.centerPx.y,
    right.centerPx.x - previousMatch.right.centerPx.x,
    right.centerPx.y - previousMatch.right.centerPx.y,
  );
}

function pointPosition(point: TriangulatedBallPoint3D | Vector3): Vector3 {
  if ('positionMeters' in point) {
    return point.positionMeters;
  }
  return point;
}

function distance3d(left: Vector3, right: Vector3): number {
  return Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z);
}

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}
