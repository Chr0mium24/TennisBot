import type { ImageSize, Matrix3x3, Matrix3x4, Vector3 } from './geometry.js';

export type DistortionModel = 'none' | 'opencv-radtan' | 'opencv-fisheye';

export interface CameraIntrinsics {
  cameraId: string;
  imageSize: ImageSize;
  cameraMatrix: Matrix3x3;
  distortionModel: DistortionModel;
  distortionCoefficients: number[];
  rmsReprojectionErrorPx?: number;
  calibratedAtUnixMs?: number;
  sourceArtifactId?: string;
}

export interface StereoExtrinsics {
  leftCameraId: string;
  rightCameraId: string;
  rotationLeftToRight: Matrix3x3;
  translationLeftToRightMeters: Vector3;
  baselineMeters?: number;
  rmsReprojectionErrorPx?: number;
  calibratedAtUnixMs?: number;
  sourceArtifactId?: string;
}

export interface StereoCalibration {
  left: CameraIntrinsics;
  right: CameraIntrinsics;
  extrinsics: StereoExtrinsics;
  rectifiedProjection?: RectifiedStereoProjectionMatrices;
}

export interface RectifiedStereoProjectionMatrices {
  leftCameraId: string;
  rightCameraId: string;
  leftProjectionMatrix: Matrix3x4;
  rightProjectionMatrix: Matrix3x4;
  imageSize?: ImageSize;
  baselineMeters?: number;
}
