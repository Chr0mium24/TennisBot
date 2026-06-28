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

export interface TrajectoryPredictionOptions {
  generatedAtUnixMs: number;
  gravityMetersPerSecondSquared?: number;
  horizonSec?: number;
  sampleCount?: number;
  landingSurfaceZMeters?: number;
  landingSurfaceYMeters?: number;
  surface?: LandingPoint['surface'];
}

export function predictTrajectory(
  points: TriangulatedBallPoint3D[],
  options: TrajectoryPredictionOptions,
): PredictionResult {
  if (points.length < 2) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' };
  }

  const sortedPoints = [...points].sort((a, b) => a.timestampUnixMs - b.timestampUnixMs);
  const previous = sortedPoints.at(-2);
  const current = sortedPoints.at(-1);
  if (previous === undefined || current === undefined) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires at least two 3D points.' };
  }

  const dtSec = (current.timestampUnixMs - previous.timestampUnixMs) / 1000;
  if (!Number.isFinite(dtSec) || dtSec <= 0) {
    return { status: 'invalid-input', reason: 'Trajectory prediction requires increasing point timestamps.' };
  }

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

  const velocityMetersPerSec: Vector3 = {
    x: (current.positionMeters.x - previous.positionMeters.x) / dtSec,
    y: (current.positionMeters.y - previous.positionMeters.y) / dtSec,
    z: (current.positionMeters.z - previous.positionMeters.z) / dtSec,
  };

  const predictionId = `${current.pointId}:projectile`;
  const landingTimeSec = solveLandingTimeSec(
    current.positionMeters.z,
    velocityMetersPerSec.z,
    landingSurfaceZ,
    gravity,
  );
  const sampleDurationSec = landingTimeSec ?? horizonSec;
  const samples = Array.from({ length: sampleCount }, (_, index) => {
    const tOffsetSec = (sampleDurationSec * index) / (sampleCount - 1);
    return {
      tOffsetSec,
      positionMeters: projectilePoint(current.positionMeters, velocityMetersPerSec, tOffsetSec, gravity),
      velocityMetersPerSec: {
        x: velocityMetersPerSec.x,
        y: velocityMetersPerSec.y,
        z: velocityMetersPerSec.z - gravity * tOffsetSec,
      },
    };
  });

  const curve: PredictionCurve = {
    predictionId,
    generatedAtUnixMs: options.generatedAtUnixMs,
    sourcePointIds: sortedPoints.map((point) => point.pointId),
    model: 'projectile-3d-constant-gravity',
    quality: qualityForPoints(sortedPoints),
    samples,
  };

  const landingPoint =
    landingTimeSec === null
      ? null
      : {
          landingId: `${predictionId}:landing`,
          generatedAtUnixMs: options.generatedAtUnixMs,
          positionMeters: {
            ...projectilePoint(current.positionMeters, velocityMetersPerSec, landingTimeSec, gravity),
            z: landingSurfaceZ,
          },
          tOffsetSec: landingTimeSec,
          confidence: confidenceForPoints(sortedPoints),
          surface: options.surface ?? 'court',
          sourcePredictionId: predictionId,
        };

  return { status: 'ok', curve, landingPoint };
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
