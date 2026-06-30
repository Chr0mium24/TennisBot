import type {
  LandingPoint,
  PredictionCurve,
  TriangulatedBallPoint3D,
  Vector3,
} from '../../contracts/src/index.js';

export type PredictionResult =
  | {
      status: 'ok';
      curve: PredictionCurve;
      landingPoint: LandingPoint | null;
    }
  | {
      status: 'invalid-input';
      reason: string;
    };

export type TrajectoryPredictionMethod = 'auto' | 'two-frame' | 'weighted-ls' | 'ransac-ls';

export interface TrajectoryPredictionOptions {
  generatedAtUnixMs: number;
  gravityMetersPerSecondSquared?: number;
  horizonSec?: number;
  sampleCount?: number;
  landingSurfaceZMeters?: number;
  landingSurfaceYMeters?: number;
  surface?: LandingPoint['surface'];
  method?: TrajectoryPredictionMethod;
  weightedWindowSize?: number;
  minWeightedFitPoints?: number;
  ransacWindowSize?: number;
  minRansacPoints?: number;
  ransacSubsetSize?: number;
  ransacIterations?: number;
  ransacThresholdMeters?: number;
}

type ResolvedPredictionOptions = {
  generatedAtUnixMs: number;
  gravityMetersPerSecondSquared: number;
  horizonSec: number;
  sampleCount: number;
  landingSurfaceZMeters: number;
  surface?: LandingPoint['surface'];
  method: TrajectoryPredictionMethod;
  weightedWindowSize: number;
  minWeightedFitPoints: number;
  ransacWindowSize: number;
  minRansacPoints: number;
  ransacSubsetSize: number;
  ransacIterations?: number;
  ransacThresholdMeters: number;
};

type ProjectileStateEstimate = {
  positionMeters: Vector3;
  velocityMetersPerSec: Vector3;
  sourcePoints: TriangulatedBallPoint3D[];
  model: string;
  residualMeters: number;
  inlierCount: number;
};

type FitResult = {
  positionMeters: Vector3;
  velocityMetersPerSec: Vector3;
  residualMeters: number;
};

const DEFAULT_WEIGHTED_WINDOW_SIZE = 9;
const DEFAULT_MIN_WEIGHTED_FIT_POINTS = 5;
const DEFAULT_RANSAC_WINDOW_SIZE = 12;
const DEFAULT_MIN_RANSAC_POINTS = 6;
const DEFAULT_RANSAC_SUBSET_SIZE = 4;
const DEFAULT_RANSAC_THRESHOLD_METERS = 0.12;

export function predictTrajectory(
  points: TriangulatedBallPoint3D[],
  options: TrajectoryPredictionOptions,
): PredictionResult {
  if (points.length < 2) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' };
  }

  const sortedPoints = [...points].sort((a, b) => a.timestampUnixMs - b.timestampUnixMs);
  const current = sortedPoints.at(-1);
  if (current === undefined) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' };
  }

  const resolved = resolveOptions(options);
  if (resolved.status === 'invalid-input') return resolved;

  const estimate = estimateProjectileState(sortedPoints, resolved.options);
  if (estimate.status === 'invalid-input') return estimate;

  const predictionSource = estimate.value.sourcePoints.at(-1) ?? current;
  const predictionId = `${predictionSource.pointId}:projectile`;
  const landingTimeSec = solveLandingTimeSec(
    estimate.value.positionMeters.z,
    estimate.value.velocityMetersPerSec.z,
    resolved.options.landingSurfaceZMeters,
    resolved.options.gravityMetersPerSecondSquared,
  );
  const sampleDurationSec = landingTimeSec ?? resolved.options.horizonSec;
  const samples = Array.from({ length: resolved.options.sampleCount }, (_, index) => {
    const tOffsetSec = (sampleDurationSec * index) / (resolved.options.sampleCount - 1);
    return {
      tOffsetSec,
      positionMeters: projectilePoint(
        estimate.value.positionMeters,
        estimate.value.velocityMetersPerSec,
        tOffsetSec,
        resolved.options.gravityMetersPerSecondSquared,
      ),
      velocityMetersPerSec: {
        x: estimate.value.velocityMetersPerSec.x,
        y: estimate.value.velocityMetersPerSec.y,
        z: estimate.value.velocityMetersPerSec.z - resolved.options.gravityMetersPerSecondSquared * tOffsetSec,
      },
    };
  });

  const curve: PredictionCurve = {
    predictionId,
    generatedAtUnixMs: resolved.options.generatedAtUnixMs,
    sourcePointIds: estimate.value.sourcePoints.map((point) => point.pointId),
    model: estimate.value.model,
    quality: qualityForPoints(estimate.value.sourcePoints),
    samples,
  };

  const landingPoint =
    landingTimeSec === null
      ? null
      : {
          landingId: `${predictionId}:landing`,
          generatedAtUnixMs: resolved.options.generatedAtUnixMs,
          positionMeters: {
            ...projectilePoint(
              estimate.value.positionMeters,
              estimate.value.velocityMetersPerSec,
              landingTimeSec,
              resolved.options.gravityMetersPerSecondSquared,
            ),
            z: resolved.options.landingSurfaceZMeters,
          },
          tOffsetSec: landingTimeSec,
          confidence: confidenceForPoints(estimate.value.sourcePoints),
          surface: resolved.options.surface ?? 'court',
          sourcePredictionId: predictionId,
        };

  return { status: 'ok', curve, landingPoint };
}

function resolveOptions(
  options: TrajectoryPredictionOptions,
): { status: 'ok'; options: ResolvedPredictionOptions } | { status: 'invalid-input'; reason: string } {
  const gravity = options.gravityMetersPerSecondSquared ?? 9.81;
  if (!Number.isFinite(gravity) || gravity <= 0) {
    return { status: 'invalid-input', reason: 'Gravity must be a positive finite value.' };
  }

  const horizonSec = options.horizonSec ?? 1;
  if (!Number.isFinite(horizonSec) || horizonSec <= 0) {
    return { status: 'invalid-input', reason: 'Prediction horizon must be a positive finite value.' };
  }

  const sampleCount = options.sampleCount ?? 21;
  if (!Number.isInteger(sampleCount) || sampleCount < 2) {
    return { status: 'invalid-input', reason: 'Prediction sample count must be an integer of at least 2.' };
  }

  const landingSurfaceZ = options.landingSurfaceZMeters ?? options.landingSurfaceYMeters ?? 0;
  if (!Number.isFinite(landingSurfaceZ)) {
    return { status: 'invalid-input', reason: 'Landing surface height must be finite.' };
  }

  const method = options.method ?? 'auto';
  const weightedWindowSize = options.weightedWindowSize ?? DEFAULT_WEIGHTED_WINDOW_SIZE;
  if (!Number.isInteger(weightedWindowSize) || weightedWindowSize < 2) {
    return { status: 'invalid-input', reason: 'Weighted LS window size must be an integer of at least 2.' };
  }

  const minWeightedFitPoints = options.minWeightedFitPoints ?? DEFAULT_MIN_WEIGHTED_FIT_POINTS;
  if (!Number.isInteger(minWeightedFitPoints) || minWeightedFitPoints < 2) {
    return { status: 'invalid-input', reason: 'Weighted LS minimum point count must be an integer of at least 2.' };
  }

  const ransacWindowSize = options.ransacWindowSize ?? DEFAULT_RANSAC_WINDOW_SIZE;
  if (!Number.isInteger(ransacWindowSize) || ransacWindowSize < 2) {
    return { status: 'invalid-input', reason: 'RANSAC window size must be an integer of at least 2.' };
  }

  const minRansacPoints = options.minRansacPoints ?? DEFAULT_MIN_RANSAC_POINTS;
  if (!Number.isInteger(minRansacPoints) || minRansacPoints < 2) {
    return { status: 'invalid-input', reason: 'RANSAC minimum point count must be an integer of at least 2.' };
  }

  const ransacSubsetSize = options.ransacSubsetSize ?? DEFAULT_RANSAC_SUBSET_SIZE;
  if (!Number.isInteger(ransacSubsetSize) || ransacSubsetSize < 2) {
    return { status: 'invalid-input', reason: 'RANSAC subset size must be an integer of at least 2.' };
  }

  if (options.ransacIterations !== undefined && (!Number.isInteger(options.ransacIterations) || options.ransacIterations <= 0)) {
    return { status: 'invalid-input', reason: 'RANSAC iteration count must be a positive integer.' };
  }

  const ransacThresholdMeters = options.ransacThresholdMeters ?? DEFAULT_RANSAC_THRESHOLD_METERS;
  if (!Number.isFinite(ransacThresholdMeters) || ransacThresholdMeters <= 0) {
    return { status: 'invalid-input', reason: 'RANSAC threshold must be a positive finite value.' };
  }

  return {
    status: 'ok',
    options: {
      generatedAtUnixMs: options.generatedAtUnixMs,
      gravityMetersPerSecondSquared: gravity,
      horizonSec,
      sampleCount,
      landingSurfaceZMeters: landingSurfaceZ,
      surface: options.surface,
      method,
      weightedWindowSize,
      minWeightedFitPoints,
      ransacWindowSize,
      minRansacPoints,
      ransacSubsetSize,
      ransacIterations: options.ransacIterations,
      ransacThresholdMeters,
    },
  };
}

function estimateProjectileState(
  sortedPoints: TriangulatedBallPoint3D[],
  options: ResolvedPredictionOptions,
): { status: 'ok'; value: ProjectileStateEstimate } | { status: 'invalid-input'; reason: string } {
  const twoFrame = fitTwoFrame(sortedPoints);
  if (twoFrame.status === 'invalid-input') return twoFrame;

  if (options.method === 'two-frame') {
    return { status: 'ok', value: twoFrame.value };
  }

  const weighted = fitWeightedWindow(sortedPoints, options);
  if (options.method === 'weighted-ls') {
    if (weighted === null) {
      return {
        status: 'invalid-input',
        reason: `Weighted LS prediction requires at least ${options.minWeightedFitPoints} 3D points.`,
      };
    }
    return { status: 'ok', value: weighted };
  }

  const ransac = fitRansacGuard(sortedPoints, options);
  if (options.method === 'ransac-ls') {
    if (ransac === null) {
      return {
        status: 'invalid-input',
        reason: `RANSAC LS prediction requires at least ${options.minRansacPoints} 3D points.`,
      };
    }
    return { status: 'ok', value: ransac };
  }

  if (ransac !== null) return { status: 'ok', value: ransac };
  if (weighted !== null) return { status: 'ok', value: weighted };
  return { status: 'ok', value: twoFrame.value };
}

function fitTwoFrame(
  sortedPoints: TriangulatedBallPoint3D[],
): { status: 'ok'; value: ProjectileStateEstimate } | { status: 'invalid-input'; reason: string } {
  const previous = sortedPoints.at(-2);
  const current = sortedPoints.at(-1);
  if (previous === undefined || current === undefined) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' };
  }

  const dtSec = (current.timestampUnixMs - previous.timestampUnixMs) / 1000;
  if (!Number.isFinite(dtSec) || dtSec <= 0) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires increasing point timestamps.' };
  }

  return {
    status: 'ok',
    value: {
      positionMeters: current.positionMeters,
      velocityMetersPerSec: {
        x: (current.positionMeters.x - previous.positionMeters.x) / dtSec,
        y: (current.positionMeters.y - previous.positionMeters.y) / dtSec,
        z: (current.positionMeters.z - previous.positionMeters.z) / dtSec,
      },
      sourcePoints: [previous, current],
      model: 'projectile-3d-two-frame-constant-gravity',
      residualMeters: 0,
      inlierCount: 2,
    },
  };
}

function fitWeightedWindow(
  sortedPoints: TriangulatedBallPoint3D[],
  options: ResolvedPredictionOptions,
): ProjectileStateEstimate | null {
  const window = sortedPoints.slice(-options.weightedWindowSize);
  if (window.length < options.minWeightedFitPoints) return null;

  const current = sortedPoints.at(-1);
  if (current === undefined) return null;

  const fit = fitFixedGravity(window, {
    gravityMetersPerSecondSquared: options.gravityMetersPerSecondSquared,
    referenceUnixMs: current.timestampUnixMs,
    weighted: true,
  });
  if (fit === null) return null;

  return {
    ...fit,
    sourcePoints: window,
    model: 'projectile-3d-weighted-ls9-constant-gravity',
    inlierCount: window.length,
  };
}

function fitRansacGuard(
  sortedPoints: TriangulatedBallPoint3D[],
  options: ResolvedPredictionOptions,
): ProjectileStateEstimate | null {
  const current = sortedPoints.at(-1);
  if (current === undefined) return null;

  const window = sortedPoints.slice(-options.ransacWindowSize);
  if (window.length < options.minRansacPoints || window.length < options.ransacSubsetSize) return null;

  const subsets = candidateSubsets(window, options.ransacSubsetSize, options.ransacIterations);
  let best:
    | {
        fit: FitResult;
        fitSamples: TriangulatedBallPoint3D[];
        inlierCount: number;
      }
    | null = null;

  for (const subset of subsets) {
    const candidate = fitFixedGravity(subset, {
      gravityMetersPerSecondSquared: options.gravityMetersPerSecondSquared,
      referenceUnixMs: current.timestampUnixMs,
      weighted: false,
    });
    if (candidate === null) continue;

    const inliers = window.filter(
      (point) =>
        trajectoryResidualMeters(
          point,
          current.timestampUnixMs,
          candidate.positionMeters,
          candidate.velocityMetersPerSec,
          options.gravityMetersPerSecondSquared,
        ) <= options.ransacThresholdMeters,
    );
    if (inliers.length < options.minWeightedFitPoints) continue;

    const fitSamples = inliers.slice(-options.weightedWindowSize);
    const refined = fitFixedGravity(fitSamples, {
      gravityMetersPerSecondSquared: options.gravityMetersPerSecondSquared,
      referenceUnixMs: current.timestampUnixMs,
      weighted: true,
    });
    if (refined === null) continue;

    if (
      best === null ||
      inliers.length > best.inlierCount ||
      (inliers.length === best.inlierCount && refined.residualMeters < best.fit.residualMeters)
    ) {
      best = { fit: refined, fitSamples, inlierCount: inliers.length };
    }
  }

  if (best === null) return null;
  if (best.inlierCount < Math.max(options.minWeightedFitPoints, Math.ceil(window.length * 0.5))) return null;

  return {
    ...best.fit,
    sourcePoints: best.fitSamples,
    model: 'projectile-3d-weighted-ls9-ransac-constant-gravity',
    inlierCount: best.inlierCount,
  };
}

function fitFixedGravity(
  samples: TriangulatedBallPoint3D[],
  options: {
    gravityMetersPerSecondSquared: number;
    referenceUnixMs: number;
    weighted: boolean;
  },
): FitResult | null {
  if (samples.length < 2) return null;

  const sorted = [...samples].sort((a, b) => a.timestampUnixMs - b.timestampUnixMs);
  const taus = sorted.map((sample) => (sample.timestampUnixMs - options.referenceUnixMs) / 1000);
  const weights = sorted.map((sample, index) => {
    if (!options.weighted) return 1;
    const ageSec = Math.max(0, (options.referenceUnixMs - sample.timestampUnixMs) / 1000);
    return Math.exp(-ageSec / 0.18) * (0.6 + (index + 1) / sorted.length);
  });
  const xFit = weightedLineFit(
    taus,
    sorted.map((sample) => sample.positionMeters.x),
    weights,
  );
  const yFit = weightedLineFit(
    taus,
    sorted.map((sample) => sample.positionMeters.y),
    weights,
  );
  const zFit = weightedLineFit(
    taus,
    sorted.map(
      (sample, index) =>
        sample.positionMeters.z + 0.5 * options.gravityMetersPerSecondSquared * taus[index] * taus[index],
    ),
    weights,
  );
  if (xFit === null || yFit === null || zFit === null) return null;

  const positionMeters = {
    x: xFit.intercept,
    y: yFit.intercept,
    z: zFit.intercept,
  };
  const velocityMetersPerSec = {
    x: xFit.slope,
    y: yFit.slope,
    z: zFit.slope,
  };
  const residualMeters =
    sorted.reduce(
      (sum, point) =>
        sum +
        trajectoryResidualMeters(
          point,
          options.referenceUnixMs,
          positionMeters,
          velocityMetersPerSec,
          options.gravityMetersPerSecondSquared,
        ),
      0,
    ) / sorted.length;

  return { positionMeters, velocityMetersPerSec, residualMeters };
}

function weightedLineFit(xs: number[], ys: number[], weights: number[]): { intercept: number; slope: number } | null {
  let weightSum = 0;
  let weightedXSum = 0;
  let weightedYSum = 0;
  let weightedX2Sum = 0;
  let weightedXySum = 0;

  for (let index = 0; index < xs.length; index += 1) {
    const weight = weights[index];
    const x = xs[index];
    const y = ys[index];
    if (!Number.isFinite(weight) || !Number.isFinite(x) || !Number.isFinite(y)) return null;
    weightSum += weight;
    weightedXSum += weight * x;
    weightedYSum += weight * y;
    weightedX2Sum += weight * x * x;
    weightedXySum += weight * x * y;
  }

  const denominator = weightSum * weightedX2Sum - weightedXSum * weightedXSum;
  if (Math.abs(denominator) < 1e-12) return null;

  return {
    intercept: (weightedYSum - ((weightSum * weightedXySum - weightedXSum * weightedYSum) / denominator) * weightedXSum) / weightSum,
    slope: (weightSum * weightedXySum - weightedXSum * weightedYSum) / denominator,
  };
}

function candidateSubsets<T>(items: T[], subsetSize: number, iterationLimit: number | undefined): T[][] {
  const subsets: T[][] = [];
  const indices: number[] = [];
  const limit = iterationLimit ?? (items.length <= DEFAULT_RANSAC_WINDOW_SIZE ? Number.POSITIVE_INFINITY : 240);

  function visit(start: number): void {
    if (subsets.length >= limit) return;
    if (indices.length === subsetSize) {
      subsets.push(indices.map((index) => items[index]));
      return;
    }

    const remaining = subsetSize - indices.length;
    for (let index = start; index <= items.length - remaining; index += 1) {
      indices.push(index);
      visit(index + 1);
      indices.pop();
      if (subsets.length >= limit) return;
    }
  }

  visit(0);
  return subsets;
}

function trajectoryResidualMeters(
  point: TriangulatedBallPoint3D,
  referenceUnixMs: number,
  positionMeters: Vector3,
  velocityMetersPerSec: Vector3,
  gravityMetersPerSecondSquared: number,
): number {
  const tSec = (point.timestampUnixMs - referenceUnixMs) / 1000;
  const predicted = projectilePoint(positionMeters, velocityMetersPerSec, tSec, gravityMetersPerSecondSquared);
  return distanceMeters(predicted, point.positionMeters);
}

function distanceMeters(left: Vector3, right: Vector3): number {
  return Math.hypot(left.x - right.x, left.y - right.y, left.z - right.z);
}

function projectilePoint(position: Vector3, velocity: Vector3, tSec: number, gravity: number): Vector3 {
  // Coordinate convention: x is lateral, y is forward/depth, z is vertical-up in meters.
  // Gravity acts in negative z, matching BallTrajectoryLab's projectile predictor.
  return {
    x: position.x + velocity.x * tSec,
    y: position.y + velocity.y * tSec,
    z: position.z + velocity.z * tSec - 0.5 * gravity * tSec * tSec,
  };
}

function solveLandingTimeSec(z0: number, vz0: number, landingSurfaceZ: number, gravity: number): number | null {
  const relativeZ = z0 - landingSurfaceZ;
  const discriminant = vz0 * vz0 + 2 * gravity * relativeZ;
  if (discriminant < 0) {
    return null;
  }

  const sqrtDiscriminant = Math.sqrt(discriminant);
  const candidates = [(vz0 + sqrtDiscriminant) / gravity, (vz0 - sqrtDiscriminant) / gravity].filter(
    (value) => value > 0,
  );
  return candidates.length > 0 ? Math.min(...candidates) : null;
}

function qualityForPoints(points: TriangulatedBallPoint3D[]): PredictionCurve['quality'] {
  const confidence = confidenceForPoints(points);
  if (confidence >= 0.8) {
    return 'high';
  }
  if (confidence >= 0.5) {
    return 'medium';
  }
  return 'low';
}

function confidenceForPoints(points: TriangulatedBallPoint3D[]): number {
  const reprojectionErrors = points
    .map((point) => point.reprojectionErrorPx)
    .filter((value): value is number => value !== undefined && Number.isFinite(value));
  if (reprojectionErrors.length === 0) {
    return 0.6;
  }

  const averageErrorPx = reprojectionErrors.reduce((sum, value) => sum + value, 0) / reprojectionErrors.length;
  return Math.max(0, Math.min(1, 1 - averageErrorPx / 10));
}
