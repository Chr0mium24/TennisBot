import type {
  LandingPoint,
  PredictionCurve,
  TriangulatedBallPoint3D,
} from '../../contracts/src/index.js';

export type PredictionResult =
  | {
      status: 'ok';
      curve: PredictionCurve;
      landingPoint: LandingPoint | null;
    }
  | {
      status: 'not-implemented';
      reason: string;
    };

export interface TrajectoryPredictionOptions {
  generatedAtUnixMs: number;
  gravityMetersPerSecondSquared?: number;
  landingSurfaceYMeters?: number;
}

export function predictTrajectory(
  _points: TriangulatedBallPoint3D[],
  _options: TrajectoryPredictionOptions,
): PredictionResult {
  return {
    status: 'not-implemented',
    reason: 'Trajectory and landing prediction will be migrated from BallTrajectoryLab into packages/core.',
  };
}
