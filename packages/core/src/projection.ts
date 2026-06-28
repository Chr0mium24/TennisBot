import type {
  CameraIntrinsics,
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

export function epipolarErrorRectified(leftPx: Vector2, rightPx: Vector2): number {
  return Math.abs(leftPx.y - rightPx.y);
}

export function disparityPx(leftPx: Vector2, rightPx: Vector2): number {
  return leftPx.x - rightPx.x;
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
    disparityPx: disparityPx(leftPx, rightPx),
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
    const positionMeters = triangulateRectifiedStereoPoint(
      calibration.rectifiedProjection,
      pair.left.centerPx,
      pair.right.centerPx,
    );
    const diagnostics = stereoReprojectionDiagnostics(
      calibration.rectifiedProjection,
      positionMeters,
      pair.left.centerPx,
      pair.right.centerPx,
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
