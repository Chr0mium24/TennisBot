import { describe, expect, test } from 'bun:test';
import type {
  CameraIntrinsics,
  LandingPoint,
  Matrix3x3,
  RectifiedStereoProjectionMatrices,
  PredictionCurve,
  StereoPairingDiagnostics,
  StereoExtrinsics,
  TimestampedStereoDetectionPair,
  TriangulatedBallPoint3D,
  YoloDetection2D,
} from './index.js';

const identityMatrix: Matrix3x3 = {
  values: [1, 0, 0, 0, 1, 0, 0, 0, 1],
  storage: 'row-major',
};

describe('runtime data contracts', () => {
  test('represents camera intrinsics and stereo extrinsics as plain data', () => {
    const intrinsics: CameraIntrinsics = {
      cameraId: 'cam-left',
      imageSize: { widthPx: 1280, heightPx: 720 },
      cameraMatrix: {
        values: [900, 0, 640, 0, 900, 360, 0, 0, 1],
        storage: 'row-major',
      },
      distortionModel: 'opencv-radtan',
      distortionCoefficients: [0.1, -0.03, 0, 0, 0],
      rmsReprojectionErrorPx: 0.35,
    };

    const extrinsics: StereoExtrinsics = {
      leftCameraId: 'cam-left',
      rightCameraId: 'cam-right',
      rotationLeftToRight: identityMatrix,
      translationLeftToRightMeters: { x: 0.18, y: 0, z: 0 },
      baselineMeters: 0.18,
    };

    expect(intrinsics.cameraMatrix.values).toHaveLength(9);
    expect(extrinsics.translationLeftToRightMeters.x).toBe(0.18);
  });

  test('represents row-major rectified stereo projection matrices', () => {
    const projections: RectifiedStereoProjectionMatrices = {
      leftCameraId: 'cam-left',
      rightCameraId: 'cam-right',
      leftRectificationMatrix: identityMatrix,
      rightRectificationMatrix: identityMatrix,
      leftProjectionMatrix: {
        values: [1000, 0, 640, 0, 0, 1000, 360, 0, 0, 0, 1, 0],
        storage: 'row-major',
      },
      rightProjectionMatrix: {
        values: [1000, 0, 640, -200, 0, 1000, 360, 0, 0, 0, 1, 0],
        storage: 'row-major',
      },
      baselineMeters: 0.2,
    };

    expect(projections.leftProjectionMatrix.values).toHaveLength(12);
    expect(projections.leftRectificationMatrix?.values).toHaveLength(9);
    expect(projections.rightProjectionMatrix.storage).toBe('row-major');
  });

  test('represents YOLO detections, stereo pairs, and triangulated points', () => {
    const left: YoloDetection2D = {
      detectionId: 'det-left-1',
      cameraId: 'cam-left',
      frameId: 'left-frame-42',
      timestampUnixMs: 1710000000000,
      classId: 0,
      label: 'tennis_ball',
      confidence: 0.91,
      bboxPx: { xPx: 610, yPx: 320, widthPx: 24, heightPx: 24 },
      centerPx: { x: 622, y: 332 },
    };

    const right: YoloDetection2D = {
      ...left,
      detectionId: 'det-right-1',
      cameraId: 'cam-right',
      frameId: 'right-frame-42',
      centerPx: { x: 590, y: 332 },
    };

    const pair: TimestampedStereoDetectionPair = {
      pairId: 'pair-1',
      timestampUnixMs: 1710000000002,
      left,
      right,
      maxTimestampDeltaMs: 8,
      leftRectifiedCenterPx: { x: 622, y: 332 },
      rightRectifiedCenterPx: { x: 590, y: 332 },
      matchConfidence: 0.88,
      disparityPx: 32,
      epipolarErrorPx: 0,
      matchCost: -0.7,
    };

    const point: TriangulatedBallPoint3D = {
      pointId: 'point-1',
      timestampUnixMs: pair.timestampUnixMs,
      positionMeters: { x: 0.2, y: 0.4, z: 3.1 },
      sourcePairId: pair.pairId,
      reprojectionErrorPx: 1.2,
      diagnostics: {
        disparityPx: 32,
        epipolarErrorPx: 0,
        leftReprojectionErrorPx: 1.1,
        rightReprojectionErrorPx: 1.3,
        averageReprojectionErrorPx: 1.2,
      },
    };

    expect(pair.left.label).toBe('tennis_ball');
    expect(point.sourcePairId).toBe(pair.pairId);

    const pairingDiagnostics: StereoPairingDiagnostics = {
      evaluatedCandidateCount: 4,
      rejectedByTimestampCount: 1,
      rejectedByEpipolarCount: 1,
      rejectedByDisparityCount: 1,
      rejectedByDepthCount: 0,
      rejectedByReprojectionCount: 0,
      rejectedByTriangulationCount: 0,
      bestCost: -0.7,
    };
    expect(pairingDiagnostics.rejectedByTimestampCount).toBe(1);
  });

  test('represents prediction curves and landing points', () => {
    const curve: PredictionCurve = {
      predictionId: 'pred-1',
      generatedAtUnixMs: 1710000000100,
      sourcePointIds: ['point-1', 'point-2'],
      model: 'placeholder',
      quality: 'unknown',
      samples: [
        { tOffsetSec: 0, positionMeters: { x: 0, y: 1, z: 3 } },
        { tOffsetSec: 0.1, positionMeters: { x: 0.1, y: 0.9, z: 3.2 } },
      ],
    };

    const landing: LandingPoint = {
      landingId: 'landing-1',
      generatedAtUnixMs: curve.generatedAtUnixMs,
      positionMeters: { x: 1.1, y: 0, z: 5.2 },
      tOffsetSec: 1.4,
      confidence: 0.5,
      surface: 'court',
      sourcePredictionId: curve.predictionId,
    };

    expect(curve.samples[1]?.tOffsetSec).toBe(0.1);
    expect(landing.sourcePredictionId).toBe(curve.predictionId);
  });
});
