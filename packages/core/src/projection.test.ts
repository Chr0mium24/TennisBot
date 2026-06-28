import { describe, expect, test } from 'bun:test';
import type {
  CameraIntrinsics,
  RectifiedStereoProjectionMatrices,
  StereoCalibration,
  TimestampedStereoDetectionPair,
  YoloDetection2D,
} from '../../contracts/src/index.js';
import {
  averageStereoReprojectionErrorPx,
  disparityPx,
  epipolarErrorRectified,
  normalizeImagePoint,
  projectCameraPoint,
  reprojectPoint,
  selectBestStereoPair,
  stereoReprojectionDiagnostics,
  triangulateRectifiedStereoPoint,
  triangulateStereoPair,
} from './index.js';

const leftIntrinsics: CameraIntrinsics = {
  cameraId: 'cam-left',
  imageSize: { widthPx: 1280, heightPx: 720 },
  cameraMatrix: {
    values: [1000, 0, 640, 0, 1000, 360, 0, 0, 1],
    storage: 'row-major',
  },
  distortionModel: 'none',
  distortionCoefficients: [],
};

const rectifiedProjection: RectifiedStereoProjectionMatrices = {
  leftCameraId: 'cam-left',
  rightCameraId: 'cam-right',
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

describe('projection geometry', () => {
  test('normalizes an image point using pinhole intrinsics', () => {
    expect(normalizeImagePoint(leftIntrinsics, { x: 740, y: 260 })).toEqual({
      cameraId: 'cam-left',
      x: 0.1,
      y: -0.1,
    });
  });

  test('projects a camera-frame 3D point into pixels', () => {
    expect(projectCameraPoint(leftIntrinsics, { x: 0.2, y: -0.1, z: 2 })).toEqual({
      x: 740,
      y: 310,
    });
  });

  test('rejects projection at zero depth', () => {
    expect(() => projectCameraPoint(leftIntrinsics, { x: 0, y: 0, z: 0 })).toThrow(RangeError);
  });

  test('computes rectified epipolar error and disparity', () => {
    expect(epipolarErrorRectified({ x: 690, y: 380 }, { x: 590, y: 382.5 })).toBe(2.5);
    expect(disparityPx({ x: 690, y: 380 }, { x: 590, y: 382.5 })).toBe(100);
  });

  test('reprojects a known 3D point through row-major 3x4 matrices', () => {
    expect(reprojectPoint(rectifiedProjection.leftProjectionMatrix, { x: 0.1, y: 0.04, z: 2 })).toEqual({
      x: 690,
      y: 380,
    });
    expect(reprojectPoint(rectifiedProjection.rightProjectionMatrix, { x: 0.1, y: 0.04, z: 2 })).toEqual({
      x: 590,
      y: 380,
    });
  });

  test('triangulates a known rectified stereo point without OpenCV', () => {
    const point = triangulateRectifiedStereoPoint(
      rectifiedProjection,
      { x: 690, y: 380 },
      { x: 590, y: 380 },
    );

    expect(point.x).toBeCloseTo(0.1, 10);
    expect(point.y).toBeCloseTo(0.04, 10);
    expect(point.z).toBeCloseTo(2, 10);
  });

  test('computes stereo reprojection diagnostics for a triangulated point', () => {
    const point = { x: 0.1, y: 0.04, z: 2 };
    const diagnostics = stereoReprojectionDiagnostics(
      rectifiedProjection,
      point,
      { x: 690, y: 380 },
      { x: 590, y: 380 },
    );

    expect(diagnostics.averageReprojectionErrorPx).toBeCloseTo(0, 10);
    expect(averageStereoReprojectionErrorPx(rectifiedProjection, point, { x: 690, y: 380 }, { x: 590, y: 380 }))
      .toBeCloseTo(0, 10);
  });

  test('triangulates a timestamped stereo detection pair with diagnostics', () => {
    const calibration: StereoCalibration = {
      left: leftIntrinsics,
      right: { ...leftIntrinsics, cameraId: 'cam-right' },
      extrinsics: {
        leftCameraId: 'cam-left',
        rightCameraId: 'cam-right',
        rotationLeftToRight: { values: [1, 0, 0, 0, 1, 0, 0, 0, 1], storage: 'row-major' },
        translationLeftToRightMeters: { x: 0.2, y: 0, z: 0 },
      },
      rectifiedProjection,
    };
    const pair = makePair(makeDetection('left', 'cam-left', 690, 380, 0.9), makeDetection('right', 'cam-right', 590, 380, 0.9));

    const result = triangulateStereoPair(calibration, pair);

    expect(result.status).toBe('ok');
    if (result.status === 'ok') {
      expect(result.point.positionMeters.z).toBeCloseTo(2, 10);
      expect(result.point.diagnostics?.disparityPx).toBe(100);
      expect(result.point.reprojectionErrorPx).toBeCloseTo(0, 10);
    }
  });
});

describe('stereo pairing', () => {
  test('selects the best candidate after epipolar and disparity filtering', () => {
    const leftA = makeDetection('left-a', 'cam-left', 690, 380, 0.6);
    const leftB = makeDetection('left-b', 'cam-left', 705, 382, 0.95);
    const rightBadEpipolar = makeDetection('right-bad-epi', 'cam-right', 590, 392, 0.99);
    const rightBadDisparity = makeDetection('right-bad-disp', 'cam-right', 704, 382, 0.99);
    const rightGood = makeDetection('right-good', 'cam-right', 605, 382.5, 0.9);

    const result = selectBestStereoPair({
      pairId: 'pair-selected',
      timestampUnixMs: 1710000000000,
      maxTimestampDeltaMs: 8,
      leftDetections: [leftA, leftB],
      rightDetections: [rightBadEpipolar, rightBadDisparity, rightGood],
      spec: { maxEpipolarErrorPx: 3, minDisparityPx: 10, maxDisparityPx: 160, temporalWeight: 0.25 },
    });

    expect(result.diagnostics.evaluatedCandidateCount).toBe(6);
    expect(result.match?.left.detectionId).toBe('left-b');
    expect(result.match?.right.detectionId).toBe('right-good');
    expect(result.match?.disparityPx).toBe(100);
  });

  test('uses optional temporal scoring to prefer continuity', () => {
    const previous = makePair(
      makeDetection('previous-left', 'cam-left', 690, 380, 0.9),
      makeDetection('previous-right', 'cam-right', 590, 380, 0.9),
    );
    const nearLeft = makeDetection('near-left', 'cam-left', 692, 380, 0.7);
    const nearRight = makeDetection('near-right', 'cam-right', 592, 380, 0.7);
    const farLeft = makeDetection('far-left', 'cam-left', 820, 380, 0.99);
    const farRight = makeDetection('far-right', 'cam-right', 720, 380, 0.99);

    const result = selectBestStereoPair({
      pairId: 'pair-temporal',
      timestampUnixMs: 1710000000016,
      maxTimestampDeltaMs: 8,
      leftDetections: [farLeft, nearLeft],
      rightDetections: [farRight, nearRight],
      previousMatch: previous,
      spec: { maxEpipolarErrorPx: 3, minDisparityPx: 10, maxDisparityPx: 160, temporalWeight: 0.25 },
    });

    expect(result.match?.left.detectionId).toBe('near-left');
    expect(result.match?.right.detectionId).toBe('near-right');
  });
});

function makeDetection(
  detectionId: string,
  cameraId: string,
  x: number,
  y: number,
  confidence: number,
): YoloDetection2D {
  return {
    detectionId,
    cameraId,
    frameId: `${cameraId}-frame-1`,
    timestampUnixMs: 1710000000000,
    classId: 0,
    label: 'tennis_ball',
    confidence,
    bboxPx: { xPx: x - 5, yPx: y - 5, widthPx: 10, heightPx: 10 },
    centerPx: { x, y },
  };
}

function makePair(left: YoloDetection2D, right: YoloDetection2D): TimestampedStereoDetectionPair {
  return {
    pairId: 'pair-1',
    timestampUnixMs: 1710000000000,
    left,
    right,
    maxTimestampDeltaMs: 8,
  };
}
