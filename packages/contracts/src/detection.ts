import type { PixelBoundingBox, Vector2, Vector3 } from './geometry.js';

export interface YoloDetection2D {
  detectionId: string;
  cameraId: string;
  frameId: string;
  timestampUnixMs: number;
  classId: number;
  label: string;
  confidence: number;
  bboxPx: PixelBoundingBox;
  centerPx: Vector2;
}

export interface TimestampedStereoDetectionPair {
  pairId: string;
  timestampUnixMs: number;
  left: YoloDetection2D;
  right: YoloDetection2D;
  maxTimestampDeltaMs: number;
  matchConfidence?: number;
  disparityPx?: number;
  epipolarErrorPx?: number;
  matchCost?: number;
}

export interface StereoPairingDiagnostics {
  evaluatedCandidateCount: number;
  rejectedByTimestampCount: number;
  rejectedByEpipolarCount: number;
  rejectedByDisparityCount: number;
  bestCost: number | null;
}

export interface TriangulatedBallPoint3D {
  pointId: string;
  timestampUnixMs: number;
  positionMeters: Vector3;
  sourcePairId: string;
  reprojectionErrorPx?: number;
  diagnostics?: TriangulationDiagnostics;
  covarianceMeters?: number[];
}

export interface TriangulationDiagnostics {
  disparityPx: number;
  epipolarErrorPx: number;
  leftReprojectionErrorPx: number;
  rightReprojectionErrorPx: number;
  averageReprojectionErrorPx: number;
}
