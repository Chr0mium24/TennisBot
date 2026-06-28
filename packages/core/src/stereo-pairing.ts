import type {
  StereoPairingDiagnostics,
  TimestampedStereoDetectionPair,
  YoloDetection2D,
} from '../../contracts/src/index.js';
import { disparityPx, epipolarErrorRectified } from './projection.js';

export interface StereoPairingSpec {
  maxEpipolarErrorPx: number;
  minDisparityPx: number;
  maxDisparityPx: number;
  temporalWeight: number;
}

export interface SelectStereoPairOptions {
  pairId: string;
  timestampUnixMs: number;
  maxTimestampDeltaMs: number;
  leftDetections: YoloDetection2D[];
  rightDetections: YoloDetection2D[];
  previousMatch?: TimestampedStereoDetectionPair | null;
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
};

export function selectBestStereoPair(options: SelectStereoPairOptions): SelectStereoPairResult {
  const spec = { ...DEFAULT_SPEC, ...options.spec };
  let bestMatch: TimestampedStereoDetectionPair | null = null;
  let bestCost = Number.POSITIVE_INFINITY;
  let evaluatedCandidateCount = 0;
  let rejectedByEpipolarCount = 0;
  let rejectedByDisparityCount = 0;

  for (const left of options.leftDetections) {
    for (const right of options.rightDetections) {
      evaluatedCandidateCount += 1;
      const epipolarErrorPx = epipolarErrorRectified(left.centerPx, right.centerPx);
      if (epipolarErrorPx > spec.maxEpipolarErrorPx) {
        rejectedByEpipolarCount += 1;
        continue;
      }

      const disparity = disparityPx(left.centerPx, right.centerPx);
      if (disparity < spec.minDisparityPx || disparity > spec.maxDisparityPx) {
        rejectedByDisparityCount += 1;
        continue;
      }

      let cost = epipolarErrorPx - 0.5 * (left.confidence + right.confidence);
      if (options.previousMatch !== undefined && options.previousMatch !== null) {
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
        matchConfidence: clamp01(0.5 * (left.confidence + right.confidence)),
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
      rejectedByEpipolarCount,
      rejectedByDisparityCount,
      bestCost: Number.isFinite(bestCost) ? bestCost : null,
    },
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

function clamp01(value: number): number {
  return Math.max(0, Math.min(1, value));
}
