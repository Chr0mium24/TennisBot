import { describe, expect, test } from 'bun:test';
import type { CameraIntrinsics, StereoCalibration, TimestampedStereoDetectionPair } from '../../contracts/src/index.js';
import { normalizeImagePoint, projectCameraPoint, triangulateStereoPair } from './index.js';

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

describe('projection geometry placeholders', () => {
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

  test('keeps triangulation explicitly unimplemented', () => {
    const calibration: StereoCalibration = {
      left: leftIntrinsics,
      right: { ...leftIntrinsics, cameraId: 'cam-right' },
      extrinsics: {
        leftCameraId: 'cam-left',
        rightCameraId: 'cam-right',
        rotationLeftToRight: { values: [1, 0, 0, 0, 1, 0, 0, 0, 1], storage: 'row-major' },
        translationLeftToRightMeters: { x: 0.2, y: 0, z: 0 },
      },
    };
    const pair: TimestampedStereoDetectionPair = {
      pairId: 'pair-1',
      timestampUnixMs: 1710000000000,
      maxTimestampDeltaMs: 8,
      left: {
        detectionId: 'left',
        cameraId: 'cam-left',
        frameId: 'left-frame',
        timestampUnixMs: 1710000000000,
        classId: 0,
        label: 'tennis_ball',
        confidence: 0.9,
        bboxPx: { xPx: 0, yPx: 0, widthPx: 10, heightPx: 10 },
        centerPx: { x: 650, y: 360 },
      },
      right: {
        detectionId: 'right',
        cameraId: 'cam-right',
        frameId: 'right-frame',
        timestampUnixMs: 1710000000001,
        classId: 0,
        label: 'tennis_ball',
        confidence: 0.9,
        bboxPx: { xPx: 0, yPx: 0, widthPx: 10, heightPx: 10 },
        centerPx: { x: 610, y: 360 },
      },
    };

    expect(triangulateStereoPair(calibration, pair)).toEqual({
      status: 'not-implemented',
      reason: 'Stereo triangulation will be migrated from BallTrajectoryLab into packages/core.',
    });
  });
});
