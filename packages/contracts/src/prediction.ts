import type { Vector3 } from './geometry.js';

export type PredictionQuality = 'unknown' | 'low' | 'medium' | 'high';

export interface PredictionSample {
  tOffsetSec: number;
  positionMeters: Vector3;
  velocityMetersPerSec?: Vector3;
}

export interface PredictionCurve {
  predictionId: string;
  generatedAtUnixMs: number;
  sourcePointIds: string[];
  model: string;
  quality: PredictionQuality;
  samples: PredictionSample[];
}

export interface LandingPoint {
  landingId: string;
  generatedAtUnixMs: number;
  positionMeters: Vector3;
  tOffsetSec: number;
  confidence: number;
  surface: 'court' | 'floor' | 'unknown';
  sourcePredictionId: string;
}
