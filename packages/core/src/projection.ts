import type {
  CameraIntrinsics,
  ImageSize,
  Matrix3x3,
  Matrix3x4,
  RectifiedStereoProjectionMatrices,
  StereoCalibration,
  TimestampedStereoDetectionPair,
  TriangulationDiagnostics,
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
      status: 'invalid-input';
      reason: string;
    };

export function normalizeImagePoint(intrinsics: CameraIntrinsics, pointPx: Vector2): NormalizedImagePoint {
  const [fx, skew, cx, , fy, cy] = intrinsics.cameraMatrix.values;
  const y = (pointPx.y - cy) / fy;

  return {
    cameraId: intrinsics.cameraId,
    x: (pointPx.x - cx - skew * y) / fx,
    y,
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

export function epipolarErrorRectified(leftPx: Vector2, rightPx: Vector2): number {
  return Math.abs(leftPx.y - rightPx.y);
}

export function disparityPx(leftPx: Vector2, rightPx: Vector2): number {
  return leftPx.x - rightPx.x;
}

export function rectifiedDisparityPx(
  projections: RectifiedStereoProjectionMatrices,
  leftPx: Vector2,
  rightPx: Vector2,
): number {
  const sign = projections.rightProjectionMatrix.values[3] > 0 ? -1 : 1;
  return sign * disparityPx(leftPx, rightPx);
}

export function rectifyImagePoint(
  intrinsics: CameraIntrinsics,
  rectificationMatrix: Matrix3x3,
  projectionMatrix: Matrix3x4,
  pointPx: Vector2,
): Vector2 {
  const normalized = undistortNormalizedPoint(intrinsics, pointPx);
  const ray = multiplyMatrix3x3Vector(rectificationMatrix, {
    x: normalized.x,
    y: normalized.y,
    z: 1,
  });
  const p = projectionMatrix.values;
  const x = p[0] * ray.x + p[1] * ray.y + p[2] * ray.z;
  const y = p[4] * ray.x + p[5] * ray.y + p[6] * ray.z;
  const w = p[8] * ray.x + p[9] * ray.y + p[10] * ray.z;

  if (!Number.isFinite(w) || Math.abs(w) < 1e-9) {
    throw new RangeError('Point cannot be rectified because homogeneous depth is zero.');
  }

  return { x: x / w, y: y / w };
}

export function scaleCameraIntrinsicsForImageSize(
  intrinsics: CameraIntrinsics,
  targetImageSize: ImageSize,
): CameraIntrinsics {
  assertPositiveImageSize(targetImageSize);
  const scaleX = targetImageSize.widthPx / intrinsics.imageSize.widthPx;
  const scaleY = targetImageSize.heightPx / intrinsics.imageSize.heightPx;
  const matrix = intrinsics.cameraMatrix.values;

  return {
    ...intrinsics,
    imageSize: targetImageSize,
    cameraMatrix: {
      ...intrinsics.cameraMatrix,
      values: [
        matrix[0] * scaleX,
        matrix[1] * scaleX,
        matrix[2] * scaleX,
        matrix[3] * scaleY,
        matrix[4] * scaleY,
        matrix[5] * scaleY,
        matrix[6],
        matrix[7],
        matrix[8],
      ],
    },
  };
}

export function scaleRectifiedProjectionForImageSize(
  projections: RectifiedStereoProjectionMatrices,
  targetImageSize: ImageSize,
): RectifiedStereoProjectionMatrices {
  assertPositiveImageSize(targetImageSize);
  if (projections.imageSize === undefined) {
    return {
      ...projections,
      imageSize: targetImageSize,
    };
  }

  const scaleX = targetImageSize.widthPx / projections.imageSize.widthPx;
  const scaleY = targetImageSize.heightPx / projections.imageSize.heightPx;

  return {
    ...projections,
    imageSize: targetImageSize,
    leftProjectionMatrix: scaleProjectionMatrix(projections.leftProjectionMatrix, scaleX, scaleY),
    rightProjectionMatrix: scaleProjectionMatrix(projections.rightProjectionMatrix, scaleX, scaleY),
  };
}

export function scaleStereoCalibrationForImageSize(
  calibration: StereoCalibration,
  targetImageSize: ImageSize,
): StereoCalibration {
  return {
    ...calibration,
    left: scaleCameraIntrinsicsForImageSize(calibration.left, targetImageSize),
    right: scaleCameraIntrinsicsForImageSize(calibration.right, targetImageSize),
    rectifiedProjection:
      calibration.rectifiedProjection === undefined
        ? undefined
        : scaleRectifiedProjectionForImageSize(calibration.rectifiedProjection, targetImageSize),
  };
}

export function reprojectPoint(projection: Matrix3x4, pointMeters: Vector3): Vector2 {
  const p = projection.values;
  const x = p[0] * pointMeters.x + p[1] * pointMeters.y + p[2] * pointMeters.z + p[3];
  const y = p[4] * pointMeters.x + p[5] * pointMeters.y + p[6] * pointMeters.z + p[7];
  const w = p[8] * pointMeters.x + p[9] * pointMeters.y + p[10] * pointMeters.z + p[11];

  if (!Number.isFinite(w) || Math.abs(w) < 1e-9) {
    throw new RangeError('Point cannot be reprojected because homogeneous depth is zero.');
  }

  return { x: x / w, y: y / w };
}

export function stereoReprojectionDiagnostics(
  projections: RectifiedStereoProjectionMatrices,
  pointMeters: Vector3,
  leftPx: Vector2,
  rightPx: Vector2,
): TriangulationDiagnostics {
  const leftReprojected = reprojectPoint(projections.leftProjectionMatrix, pointMeters);
  const rightReprojected = reprojectPoint(projections.rightProjectionMatrix, pointMeters);
  const leftReprojectionErrorPx = distancePx(leftReprojected, leftPx);
  const rightReprojectionErrorPx = distancePx(rightReprojected, rightPx);

  return {
    disparityPx: rectifiedDisparityPx(projections, leftPx, rightPx),
    epipolarErrorPx: epipolarErrorRectified(leftPx, rightPx),
    leftReprojectionErrorPx,
    rightReprojectionErrorPx,
    averageReprojectionErrorPx: (leftReprojectionErrorPx + rightReprojectionErrorPx) / 2,
  };
}

export function averageStereoReprojectionErrorPx(
  projections: RectifiedStereoProjectionMatrices,
  pointMeters: Vector3,
  leftPx: Vector2,
  rightPx: Vector2,
): number {
  return stereoReprojectionDiagnostics(projections, pointMeters, leftPx, rightPx).averageReprojectionErrorPx;
}

export function triangulateRectifiedStereoPoint(
  projections: RectifiedStereoProjectionMatrices,
  leftPx: Vector2,
  rightPx: Vector2,
): Vector3 {
  const rows = [
    projectionEquationRow(projections.leftProjectionMatrix, leftPx.x, 0),
    projectionEquationRow(projections.leftProjectionMatrix, leftPx.y, 1),
    projectionEquationRow(projections.rightProjectionMatrix, rightPx.x, 0),
    projectionEquationRow(projections.rightProjectionMatrix, rightPx.y, 1),
  ];

  const normalA: [[number, number, number], [number, number, number], [number, number, number]] = [
    [0, 0, 0],
    [0, 0, 0],
    [0, 0, 0],
  ];
  const normalB: [number, number, number] = [0, 0, 0];

  for (const row of rows) {
    for (let r = 0; r < 3; r += 1) {
      normalB[r] += row.a[r] * row.b;
      for (let c = 0; c < 3; c += 1) {
        normalA[r][c] += row.a[r] * row.a[c];
      }
    }
  }

  const [x, y, z] = solve3x3(normalA, normalB);
  return { x, y, z };
}

export function triangulateStereoPair(
  calibration: StereoCalibration,
  pair: TimestampedStereoDetectionPair,
): TriangulationResult {
  if (calibration.rectifiedProjection === undefined) {
    return {
      status: 'invalid-input',
      reason: 'Stereo triangulation requires rectified 3x4 projection matrices.',
    };
  }

  try {
    const leftPx = pair.leftRectifiedCenterPx ?? pair.left.centerPx;
    const rightPx = pair.rightRectifiedCenterPx ?? pair.right.centerPx;
    const positionMeters = triangulateRectifiedStereoPoint(
      calibration.rectifiedProjection,
      leftPx,
      rightPx,
    );
    const diagnostics = stereoReprojectionDiagnostics(
      calibration.rectifiedProjection,
      positionMeters,
      leftPx,
      rightPx,
    );

    return {
      status: 'ok',
      point: {
        pointId: `${pair.pairId}:triangulated`,
        timestampUnixMs: pair.timestampUnixMs,
        positionMeters,
        sourcePairId: pair.pairId,
        reprojectionErrorPx: diagnostics.averageReprojectionErrorPx,
        diagnostics,
      },
    };
  } catch (error) {
    return {
      status: 'invalid-input',
      reason: error instanceof Error ? error.message : 'Stereo triangulation failed.',
    };
  }
}

function distancePx(a: Vector2, b: Vector2): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

function undistortNormalizedPoint(intrinsics: CameraIntrinsics, pointPx: Vector2): Vector2 {
  const distorted = normalizeImagePoint(intrinsics, pointPx);
  if (intrinsics.distortionModel === 'none') {
    return { x: distorted.x, y: distorted.y };
  }
  if (intrinsics.distortionModel === 'opencv-fisheye') {
    throw new RangeError('OpenCV fisheye rectification is not supported by the TypeScript runtime.');
  }

  const [k1 = 0, k2 = 0, p1 = 0, p2 = 0, k3 = 0, k4 = 0, k5 = 0, k6 = 0] =
    intrinsics.distortionCoefficients;
  let x = distorted.x;
  let y = distorted.y;

  for (let iteration = 0; iteration < 8; iteration += 1) {
    const radius2 = x * x + y * y;
    const radius4 = radius2 * radius2;
    const radius6 = radius4 * radius2;
    const radialDenominator = 1 + k1 * radius2 + k2 * radius4 + k3 * radius6;
    const radialNumerator = 1 + k4 * radius2 + k5 * radius4 + k6 * radius6;

    if (Math.abs(radialDenominator) < 1e-12 || !Number.isFinite(radialDenominator)) {
      throw new RangeError('Cannot undistort point because radial distortion is singular.');
    }

    const inverseDistortion = radialNumerator / radialDenominator;
    const deltaX = 2 * p1 * x * y + p2 * (radius2 + 2 * x * x);
    const deltaY = p1 * (radius2 + 2 * y * y) + 2 * p2 * x * y;
    x = (distorted.x - deltaX) * inverseDistortion;
    y = (distorted.y - deltaY) * inverseDistortion;
  }

  if (!Number.isFinite(x) || !Number.isFinite(y)) {
    throw new RangeError('Cannot undistort point because the normalized coordinates are not finite.');
  }

  return { x, y };
}

function multiplyMatrix3x3Vector(matrix: Matrix3x3, vector: Vector3): Vector3 {
  const m = matrix.values;
  return {
    x: m[0] * vector.x + m[1] * vector.y + m[2] * vector.z,
    y: m[3] * vector.x + m[4] * vector.y + m[5] * vector.z,
    z: m[6] * vector.x + m[7] * vector.y + m[8] * vector.z,
  };
}

function scaleProjectionMatrix(projection: Matrix3x4, scaleX: number, scaleY: number): Matrix3x4 {
  const p = projection.values;
  return {
    ...projection,
    values: [
      p[0] * scaleX,
      p[1] * scaleX,
      p[2] * scaleX,
      p[3] * scaleX,
      p[4] * scaleY,
      p[5] * scaleY,
      p[6] * scaleY,
      p[7] * scaleY,
      p[8],
      p[9],
      p[10],
      p[11],
    ],
  };
}

function assertPositiveImageSize(imageSize: ImageSize): void {
  if (
    imageSize.widthPx <= 0 ||
    imageSize.heightPx <= 0 ||
    !Number.isFinite(imageSize.widthPx) ||
    !Number.isFinite(imageSize.heightPx)
  ) {
    throw new RangeError('Image size must contain positive finite width and height.');
  }
}

function projectionEquationRow(
  projection: Matrix3x4,
  observedCoordinate: number,
  coordinateRowIndex: 0 | 1,
): { a: [number, number, number]; b: number } {
  const p = projection.values;
  const rowOffset = coordinateRowIndex * 4;
  const p3Offset = 8;

  return {
    a: [
      observedCoordinate * p[p3Offset] - p[rowOffset],
      observedCoordinate * p[p3Offset + 1] - p[rowOffset + 1],
      observedCoordinate * p[p3Offset + 2] - p[rowOffset + 2],
    ],
    b: p[rowOffset + 3] - observedCoordinate * p[p3Offset + 3],
  };
}

function solve3x3(
  matrix: [[number, number, number], [number, number, number], [number, number, number]],
  vector: [number, number, number],
): [number, number, number] {
  const augmented = matrix.map((row, index) => [...row, vector[index]]) as [
    [number, number, number, number],
    [number, number, number, number],
    [number, number, number, number],
  ];

  for (let pivotIndex = 0; pivotIndex < 3; pivotIndex += 1) {
    let bestRow = pivotIndex;
    for (let candidate = pivotIndex + 1; candidate < 3; candidate += 1) {
      if (Math.abs(augmented[candidate][pivotIndex]) > Math.abs(augmented[bestRow][pivotIndex])) {
        bestRow = candidate;
      }
    }

    if (Math.abs(augmented[bestRow][pivotIndex]) < 1e-12) {
      throw new RangeError('Triangulation equations are singular or poorly conditioned.');
    }

    if (bestRow !== pivotIndex) {
      const previous = augmented[pivotIndex];
      augmented[pivotIndex] = augmented[bestRow];
      augmented[bestRow] = previous;
    }

    const pivot = augmented[pivotIndex][pivotIndex];
    for (let column = pivotIndex; column < 4; column += 1) {
      augmented[pivotIndex][column] /= pivot;
    }

    for (let row = 0; row < 3; row += 1) {
      if (row === pivotIndex) {
        continue;
      }
      const factor = augmented[row][pivotIndex];
      for (let column = pivotIndex; column < 4; column += 1) {
        augmented[row][column] -= factor * augmented[pivotIndex][column];
      }
    }
  }

  return [augmented[0][3], augmented[1][3], augmented[2][3]];
}
