import type {
  CameraIntrinsics,
  StereoCalibration,
  TimestampedStereoDetectionPair,
  TriangulatedBallPoint3D,
  Vector2,
  Vector3,
} from '../../contracts/src/index.js';

export interface NormalizedImagePoint extends Vector2 {
  cameraId: string;
}

export type TriangulationResult =
  | {
      status: 'ok';
      point: TriangulatedBallPoint3D;
    }
  | {
      status: 'not-implemented';
      reason: string;
    };

export function normalizeImagePoint(intrinsics: CameraIntrinsics, pointPx: Vector2): NormalizedImagePoint {
  const [fx, , cx, , fy, cy] = intrinsics.cameraMatrix.values;

  return {
    cameraId: intrinsics.cameraId,
    x: (pointPx.x - cx) / fx,
    y: (pointPx.y - cy) / fy,
  };
}

export function projectCameraPoint(intrinsics: CameraIntrinsics, pointMeters: Vector3): Vector2 {
  if (pointMeters.z === 0) {
    throw new RangeError('Cannot project a point with z=0 in the camera frame.');
  }

  const [fx, , cx, , fy, cy] = intrinsics.cameraMatrix.values;

  return {
    x: (fx * pointMeters.x) / pointMeters.z + cx,
    y: (fy * pointMeters.y) / pointMeters.z + cy,
  };
}

export function triangulateStereoPair(
  _calibration: StereoCalibration,
  _pair: TimestampedStereoDetectionPair,
): TriangulationResult {
  return {
    status: 'not-implemented',
    reason: 'Stereo triangulation will be migrated from BallTrajectoryLab into packages/core.',
  };
}
