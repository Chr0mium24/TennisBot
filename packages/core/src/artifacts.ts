import type {
  ArtifactMatrix3x3Json,
  ArtifactMatrix3x4Json,
  CalibrationArtifactReference,
  CameraIntrinsics,
  CameraIntrinsicsArtifactJson,
  ImageSize,
  Matrix3x3,
  Matrix3x4,
  RectificationArtifactJson,
  RectifiedStereoProjectionMatrices,
  StereoCalibration,
  StereoCalibrationArtifactJsonBundle,
  StereoCalibrationPackageJson,
  StereoExtrinsicsArtifactJson,
  StereoVerificationArtifactJson,
  YoloLabelsJson,
  YoloModelArtifactJsonBundle,
  YoloModelArtifactReference,
  YoloPackageJson,
  YoloPostprocessingJson,
  YoloPreprocessingJson,
} from '../../contracts/src/index.js';

export interface CalibrationArtifactLoader {
  loadStereoCalibration(reference: CalibrationArtifactReference): Promise<StereoCalibration>;
}

export interface YoloModelArtifactMetadata {
  packageName: string;
  packageVersion: string;
  contractVersion: string;
  labels: string[];
  inputSizePx: ImageSize;
  inputColor: string;
  boxFormat: string;
  sourceBoxFormat?: string;
  confidenceThreshold: number;
  classId: number;
  modelPath: string;
  modelRuntime: string;
  selectedModel: string;
  modelChecks: ArtifactPendingCheck[];
}

export interface ArtifactPendingCheck {
  kind: 'file-exists' | 'sha256' | 'bytes';
  path: string;
  expected?: string | number;
  status: 'pending';
}

export interface YoloModelArtifactLoader {
  loadYoloModelMetadata(reference: YoloModelArtifactReference): Promise<YoloModelArtifactMetadata>;
}

export interface RuntimeArtifactLoaders extends CalibrationArtifactLoader, YoloModelArtifactLoader {}

export type ArtifactValidationResult<T> =
  | { ok: true; value: T; warnings: string[] }
  | { ok: false; errors: string[]; warnings: string[] };

export interface YoloArtifactParts {
  packageJson: YoloPackageJson;
  labelsJson: YoloLabelsJson;
  preprocessingJson: YoloPreprocessingJson;
  postprocessingJson: YoloPostprocessingJson;
}

export interface StereoArtifactParts {
  packageJson: StereoCalibrationPackageJson;
  cam1Json: CameraIntrinsicsArtifactJson;
  cam2Json: CameraIntrinsicsArtifactJson;
  stereoJson: StereoExtrinsicsArtifactJson;
  rectificationJson: RectificationArtifactJson;
  verificationJson?: StereoVerificationArtifactJson;
}

export function loadYoloModelArtifactMetadata(
  bundle: YoloModelArtifactJsonBundle,
): ArtifactValidationResult<YoloModelArtifactMetadata> {
  const partsResult = validateYoloModelArtifact(bundle);
  if (!partsResult.ok) {
    return partsResult;
  }

  return ok(convertYoloModelArtifactMetadata(partsResult.value), partsResult.warnings);
}

export function loadStereoCalibrationArtifact(
  bundle: StereoCalibrationArtifactJsonBundle,
): ArtifactValidationResult<StereoCalibration> {
  const partsResult = validateStereoCalibrationArtifact(bundle);
  if (!partsResult.ok) {
    return partsResult;
  }

  return ok(convertStereoCalibrationArtifact(partsResult.value), partsResult.warnings);
}

export function validateYoloModelArtifact(
  bundle: YoloModelArtifactJsonBundle,
): ArtifactValidationResult<YoloArtifactParts> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const packageJson = asRecord(bundle.packageJson, 'package.json', errors);
  const labelsJson = asRecord(bundle.labelsJson, 'labels.json', errors);
  const preprocessingJson = asRecord(bundle.preprocessingJson, 'preprocessing.json', errors);
  const postprocessingJson = asRecord(bundle.postprocessingJson, 'postprocessing.json', errors);

  if (packageJson) {
    requireString(packageJson, 'package.json.name', errors);
    requireString(packageJson, 'package.json.version', errors);
    requireLiteral(packageJson, 'package.json.contract', 'tennisbot.yolo-model-package', errors);
    requireString(packageJson, 'package.json.contract_version', errors);
    requireTimestamp(packageJson, 'package.json.created_at', errors);
    const models = asRecord(packageJson.models, 'package.json.models', errors);
    const defaultModel = requireString(packageJson, 'package.json.default_model', errors);
    requireString(packageJson, 'package.json.labels', errors);
    requireString(packageJson, 'package.json.preprocessing', errors);
    requireString(packageJson, 'package.json.postprocessing', errors);

    if (models && Object.keys(models).length === 0) {
      errors.push('package.json.models must include at least one model entry');
    }
    if (models) {
      for (const [key, value] of Object.entries(models)) {
        const model = asRecord(value, `package.json.models.${key}`, errors);
        if (!model) {
          continue;
        }
        requireString(model, `package.json.models.${key}.path`, errors);
        requireString(model, `package.json.models.${key}.runtime`, errors);
        requireString(model, `package.json.models.${key}.sha256`, errors);
        requireNumber(model, `package.json.models.${key}.bytes`, errors);
      }
      if (defaultModel && !(defaultModel in models)) {
        errors.push(`package.json.default_model '${defaultModel}' must reference package.json.models`);
      }
    }
  }

  if (labelsJson) {
    const classes = asArray(labelsJson.classes, 'labels.json.classes', errors);
    let hasTennisBallClass = false;
    classes?.forEach((value, index) => {
      const cls = asRecord(value, `labels.json.classes[${index}]`, errors);
      if (!cls) {
        return;
      }
      const id = requireNumber(cls, `labels.json.classes[${index}].id`, errors);
      const name = requireString(cls, `labels.json.classes[${index}].name`, errors);
      if (id === 0 && name === 'tennis_ball') {
        hasTennisBallClass = true;
      }
    });
    if (classes && !hasTennisBallClass) {
      errors.push('labels.json.classes must include class id 0 named tennis_ball');
    }
  }

  if (preprocessingJson) {
    requireString(preprocessingJson, 'preprocessing.json.input_color', errors);
    requireImageSize(preprocessingJson.input_size, 'preprocessing.json.input_size', errors);
    const normalization = optionalRecord(preprocessingJson.normalization, 'preprocessing.json.normalization', errors);
    if (normalization) {
      requireNumber(normalization, 'preprocessing.json.normalization.scale', errors);
      requireNumberArray(normalization.mean, 'preprocessing.json.normalization.mean', 3, errors);
      requireNumberArray(normalization.std, 'preprocessing.json.normalization.std', 3, errors);
    }
  }

  if (postprocessingJson) {
    requireNumber(postprocessingJson, 'postprocessing.json.class_id', errors);
    const confidenceThreshold = requireNumber(postprocessingJson, 'postprocessing.json.confidence_threshold', errors);
    requireString(postprocessingJson, 'postprocessing.json.box_format', errors);
    if (postprocessingJson.class_id !== 0) {
      errors.push('postprocessing.json.class_id must be 0 for tennis_ball');
    }
    if (confidenceThreshold !== undefined && (confidenceThreshold < 0 || confidenceThreshold > 1)) {
      errors.push('postprocessing.json.confidence_threshold must be between 0 and 1');
    }
  }

  if (errors.length > 0 || !packageJson || !labelsJson || !preprocessingJson || !postprocessingJson) {
    return fail(errors, warnings);
  }

  return ok(
    {
      packageJson: packageJson as unknown as YoloPackageJson,
      labelsJson: labelsJson as unknown as YoloLabelsJson,
      preprocessingJson: preprocessingJson as unknown as YoloPreprocessingJson,
      postprocessingJson: postprocessingJson as unknown as YoloPostprocessingJson,
    },
    warnings,
  );
}

export function validateStereoCalibrationArtifact(
  bundle: StereoCalibrationArtifactJsonBundle,
): ArtifactValidationResult<StereoArtifactParts> {
  const errors: string[] = [];
  const warnings: string[] = [];
  const packageJson = asRecord(bundle.packageJson, 'package.json', errors);
  const cam1Json = validateCameraIntrinsicsJson(bundle.cam1Json, 'cam1.json', errors);
  const cam2Json = validateCameraIntrinsicsJson(bundle.cam2Json, 'cam2.json', errors);
  const stereoJson = validateStereoExtrinsicsJson(bundle.stereoJson, 'stereo.json', errors);
  const rectificationJson = validateRectificationJson(bundle.rectificationJson, 'rectification.json', errors);
  const verificationJson = bundle.verificationJson === undefined
    ? undefined
    : validateStereoVerificationJson(bundle.verificationJson, 'verification.json', errors);

  if (packageJson) {
    requireLiteral(packageJson, 'package.json.schema_version', 'calibration.stereo.v1', errors);
    requireLiteral(packageJson, 'package.json.package_type', 'stereo_camera_calibration', errors);
    const cameraIds = requireStringTuple(packageJson.camera_ids, 'package.json.camera_ids', 2, errors);
    requireTimestamp(packageJson, 'package.json.created_at', errors);
    requireString(packageJson, 'package.json.source_session', errors);
    const files = asRecord(packageJson.files, 'package.json.files', errors);
    if (files) {
      requireString(files, 'package.json.files.cam1', errors);
      requireString(files, 'package.json.files.cam2', errors);
      requireString(files, 'package.json.files.stereo', errors);
      requireString(files, 'package.json.files.rectification', errors);
    }
    const quality = asRecord(packageJson.quality, 'package.json.quality', errors);
    if (quality) {
      const accepted = requireBoolean(quality, 'package.json.quality.accepted', errors);
      if (accepted === false) {
        errors.push('package.json.quality.accepted must be true for runtime loading');
      }
      optionalNumber(quality, 'package.json.quality.stereo_rms_reprojection_px', errors);
      optionalNumber(quality, 'package.json.quality.accepted_pair_count', errors);
      optionalNumber(quality, 'package.json.quality.total_pair_count', errors);
    }

    if (cameraIds && cam1Json && cam2Json) {
      if (cam1Json.camera_id !== cameraIds[0]) {
        errors.push(`cam1.json.camera_id '${cam1Json.camera_id}' must match package.json.camera_ids[0] '${cameraIds[0]}'`);
      }
      if (cam2Json.camera_id !== cameraIds[1]) {
        errors.push(`cam2.json.camera_id '${cam2Json.camera_id}' must match package.json.camera_ids[1] '${cameraIds[1]}'`);
      }
    }
  }

  if (packageJson && stereoJson) {
    const cameraIds = packageJson.camera_ids;
    if (Array.isArray(cameraIds) && cameraIds.length === 2) {
      if (stereoJson.left_camera_id !== cameraIds[0]) {
        errors.push('stereo.json.left_camera_id must match package.json.camera_ids[0]');
      }
      if (stereoJson.right_camera_id !== cameraIds[1]) {
        errors.push('stereo.json.right_camera_id must match package.json.camera_ids[1]');
      }
    }
  }

  if (packageJson && rectificationJson) {
    const cameraIds = packageJson.camera_ids;
    if (Array.isArray(cameraIds) && cameraIds.length === 2) {
      if (rectificationJson.left_camera_id !== cameraIds[0]) {
        errors.push('rectification.json.left_camera_id must match package.json.camera_ids[0]');
      }
      if (rectificationJson.right_camera_id !== cameraIds[1]) {
        errors.push('rectification.json.right_camera_id must match package.json.camera_ids[1]');
      }
    }
  }

  if (stereoJson && rectificationJson) {
    if (rectificationJson.left_camera_id !== stereoJson.left_camera_id) {
      errors.push('rectification.json.left_camera_id must match stereo.json.left_camera_id');
    }
    if (rectificationJson.right_camera_id !== stereoJson.right_camera_id) {
      errors.push('rectification.json.right_camera_id must match stereo.json.right_camera_id');
    }
  }

  if (verificationJson) {
    if (verificationJson.accepted !== true) {
      errors.push('verification.json.accepted must be true for runtime loading');
    }
    if (verificationJson.rectification?.accepted === false) {
      errors.push('verification.json.rectification.accepted must be true for runtime loading');
    }
  } else if (bundle.verificationJson === undefined) {
    warnings.push('verification.json was not provided; package.json.quality.accepted is the only acceptance gate checked');
  }

  if (
    errors.length > 0 ||
    !packageJson ||
    !cam1Json ||
    !cam2Json ||
    !stereoJson ||
    !rectificationJson
  ) {
    return fail(errors, warnings);
  }

  return ok(
    {
      packageJson: packageJson as unknown as StereoCalibrationPackageJson,
      cam1Json,
      cam2Json,
      stereoJson,
      rectificationJson,
      verificationJson,
    },
    warnings,
  );
}

export function convertCameraIntrinsicsArtifact(json: CameraIntrinsicsArtifactJson): CameraIntrinsics {
  return {
    cameraId: json.camera_id,
    imageSize: convertImageSize(json.image_size),
    cameraMatrix: matrix3x3FromArtifact(json.camera_matrix),
    distortionModel: convertDistortionModel(json.distortion_model),
    distortionCoefficients: [...json.distortion_coefficients],
  };
}

export function convertStereoCalibrationArtifact(parts: StereoArtifactParts): StereoCalibration {
  const rmsReprojectionErrorPx = parts.packageJson.quality.stereo_rms_reprojection_px;
  return {
    left: convertCameraIntrinsicsArtifact(parts.cam1Json),
    right: convertCameraIntrinsicsArtifact(parts.cam2Json),
    extrinsics: {
      leftCameraId: parts.stereoJson.left_camera_id,
      rightCameraId: parts.stereoJson.right_camera_id,
      rotationLeftToRight: matrix3x3FromArtifact(parts.stereoJson.rotation_left_to_right),
      translationLeftToRightMeters: {
        x: parts.stereoJson.translation_left_to_right_m[0],
        y: parts.stereoJson.translation_left_to_right_m[1],
        z: parts.stereoJson.translation_left_to_right_m[2],
      },
      baselineMeters: parts.stereoJson.baseline_m,
      rmsReprojectionErrorPx,
      calibratedAtUnixMs: Date.parse(parts.packageJson.created_at),
      sourceArtifactId: parts.packageJson.source_session,
    },
    rectifiedProjection: convertRectificationArtifact(parts.rectificationJson, parts.stereoJson.baseline_m),
  };
}

export function convertRectificationArtifact(
  json: RectificationArtifactJson,
  baselineMeters?: number,
): RectifiedStereoProjectionMatrices {
  return {
    leftCameraId: json.left_camera_id,
    rightCameraId: json.right_camera_id,
    leftProjectionMatrix: matrix3x4FromArtifact(json.p1),
    rightProjectionMatrix: matrix3x4FromArtifact(json.p2),
    imageSize: convertImageSize(json.image_size),
    baselineMeters,
  };
}

export function convertYoloModelArtifactMetadata(parts: YoloArtifactParts): YoloModelArtifactMetadata {
  const selectedModel = parts.packageJson.default_model;
  const model = parts.packageJson.models[selectedModel];
  if (!model) {
    throw new Error(`validated YOLO artifact is missing selected model '${selectedModel}'`);
  }

  return {
    packageName: parts.packageJson.name,
    packageVersion: parts.packageJson.version,
    contractVersion: parts.packageJson.contract_version,
    labels: parts.labelsJson.classes
      .slice()
      .sort((left, right) => left.id - right.id)
      .map((cls) => cls.name),
    inputSizePx: convertImageSize(parts.preprocessingJson.input_size),
    inputColor: parts.preprocessingJson.input_color,
    boxFormat: parts.postprocessingJson.box_format,
    sourceBoxFormat: parts.postprocessingJson.source_box_format,
    confidenceThreshold: parts.postprocessingJson.confidence_threshold,
    classId: parts.postprocessingJson.class_id,
    modelPath: model.path,
    modelRuntime: model.runtime,
    selectedModel,
    modelChecks: pendingModelChecks(model),
  };
}

export function matrix3x3FromArtifact(matrix: ArtifactMatrix3x3Json): Matrix3x3 {
  return {
    values: [
      matrix[0][0],
      matrix[0][1],
      matrix[0][2],
      matrix[1][0],
      matrix[1][1],
      matrix[1][2],
      matrix[2][0],
      matrix[2][1],
      matrix[2][2],
    ],
    storage: 'row-major',
  };
}

export function matrix3x4FromArtifact(matrix: ArtifactMatrix3x4Json): Matrix3x4 {
  return {
    values: [
      matrix[0][0],
      matrix[0][1],
      matrix[0][2],
      matrix[0][3],
      matrix[1][0],
      matrix[1][1],
      matrix[1][2],
      matrix[1][3],
      matrix[2][0],
      matrix[2][1],
      matrix[2][2],
      matrix[2][3],
    ],
    storage: 'row-major',
  };
}

function validateCameraIntrinsicsJson(
  value: unknown,
  path: string,
  errors: string[],
): CameraIntrinsicsArtifactJson | undefined {
  const json = asRecord(value, path, errors);
  if (!json) {
    return undefined;
  }

  requireLiteral(json, `${path}.schema_version`, 'calibration.camera_intrinsics.v1', errors);
  requireString(json, `${path}.camera_id`, errors);
  requireImageSize(json.image_size, `${path}.image_size`, errors);
  requireMatrix3x3(json.camera_matrix, `${path}.camera_matrix`, errors);
  const distortionModel = requireString(json, `${path}.distortion_model`, errors);
  if (distortionModel !== undefined && !isSupportedDistortionModel(distortionModel)) {
    errors.push(`${path}.distortion_model must be one of none, opencv_radtan, opencv_rational, opencv_radial_tangential, opencv_fisheye`);
  }
  requireNumberArray(json.distortion_coefficients, `${path}.distortion_coefficients`, undefined, errors);
  return json as unknown as CameraIntrinsicsArtifactJson;
}

function validateStereoExtrinsicsJson(
  value: unknown,
  path: string,
  errors: string[],
): StereoExtrinsicsArtifactJson | undefined {
  const json = asRecord(value, path, errors);
  if (!json) {
    return undefined;
  }

  requireLiteral(json, `${path}.schema_version`, 'calibration.stereo_extrinsics.v1', errors);
  requireString(json, `${path}.left_camera_id`, errors);
  requireString(json, `${path}.right_camera_id`, errors);
  requireMatrix3x3(json.rotation_left_to_right, `${path}.rotation_left_to_right`, errors);
  requireNumberArray(json.translation_left_to_right_m, `${path}.translation_left_to_right_m`, 3, errors);
  optionalNumber(json, `${path}.baseline_m`, errors);
  return json as unknown as StereoExtrinsicsArtifactJson;
}

function validateRectificationJson(
  value: unknown,
  path: string,
  errors: string[],
): RectificationArtifactJson | undefined {
  const json = asRecord(value, path, errors);
  if (!json) {
    return undefined;
  }

  requireLiteral(json, `${path}.schema_version`, 'calibration.rectification.v1', errors);
  requireString(json, `${path}.left_camera_id`, errors);
  requireString(json, `${path}.right_camera_id`, errors);
  requireImageSize(json.image_size, `${path}.image_size`, errors);
  requireMatrix3x4(json.p1, `${path}.p1`, errors);
  requireMatrix3x4(json.p2, `${path}.p2`, errors);
  return json as unknown as RectificationArtifactJson;
}

function validateStereoVerificationJson(
  value: unknown,
  path: string,
  errors: string[],
): StereoVerificationArtifactJson | undefined {
  const json = asRecord(value, path, errors);
  if (!json) {
    return undefined;
  }

  requireLiteral(json, `${path}.schema_version`, 'calibration.stereo_verification.v1', errors);
  requireBoolean(json, `${path}.accepted`, errors);
  return json as unknown as StereoVerificationArtifactJson;
}

function pendingModelChecks(model: { path: string; sha256?: string; bytes?: number }): ArtifactPendingCheck[] {
  const checks: ArtifactPendingCheck[] = [{ kind: 'file-exists', path: model.path, status: 'pending' }];
  if (model.sha256 !== undefined) {
    checks.push({ kind: 'sha256', path: model.path, expected: model.sha256, status: 'pending' });
  }
  if (model.bytes !== undefined) {
    checks.push({ kind: 'bytes', path: model.path, expected: model.bytes, status: 'pending' });
  }
  return checks;
}

function convertImageSize(size: { width: number; height: number }): ImageSize {
  return { widthPx: size.width, heightPx: size.height };
}

function convertDistortionModel(model: string): CameraIntrinsics['distortionModel'] {
  if (model === 'opencv_fisheye') {
    return 'opencv-fisheye';
  }
  if (model === 'none') {
    return 'none';
  }
  return 'opencv-radtan';
}

function ok<T>(value: T, warnings: string[] = []): ArtifactValidationResult<T> {
  return { ok: true, value, warnings };
}

function fail<T>(errors: string[], warnings: string[] = []): ArtifactValidationResult<T> {
  return { ok: false, errors: errors.length > 0 ? errors : ['artifact validation failed'], warnings };
}

function asRecord(value: unknown, path: string, errors: string[]): Record<string, unknown> | undefined {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    errors.push(`${path} must be an object`);
    return undefined;
  }
  return value as Record<string, unknown>;
}

function optionalRecord(value: unknown, path: string, errors: string[]): Record<string, unknown> | undefined {
  if (value === undefined) {
    return undefined;
  }
  return asRecord(value, path, errors);
}

function asArray(value: unknown, path: string, errors: string[]): unknown[] | undefined {
  if (!Array.isArray(value)) {
    errors.push(`${path} must be an array`);
    return undefined;
  }
  return value;
}

function requireString(record: Record<string, unknown>, path: string, errors: string[]): string | undefined {
  const key = lastPathSegment(path);
  if (typeof record[key] !== 'string' || record[key].length === 0) {
    errors.push(`${path} must be a non-empty string`);
    return undefined;
  }
  return record[key];
}

function requireTimestamp(record: Record<string, unknown>, path: string, errors: string[]): string | undefined {
  const value = requireString(record, path, errors);
  if (value !== undefined && Number.isNaN(Date.parse(value))) {
    errors.push(`${path} must be a parseable timestamp`);
  }
  return value;
}

function optionalString(record: Record<string, unknown>, path: string, errors: string[]): string | undefined {
  const key = lastPathSegment(path);
  if (record[key] === undefined) {
    return undefined;
  }
  return requireString(record, path, errors);
}

function requireNumber(record: Record<string, unknown>, path: string, errors: string[]): number | undefined {
  const key = lastPathSegment(path);
  if (typeof record[key] !== 'number' || !Number.isFinite(record[key])) {
    errors.push(`${path} must be a finite number`);
    return undefined;
  }
  return record[key];
}

function optionalNumber(record: Record<string, unknown>, path: string, errors: string[]): number | undefined {
  const key = lastPathSegment(path);
  if (record[key] === undefined) {
    return undefined;
  }
  return requireNumber(record, path, errors);
}

function requireBoolean(record: Record<string, unknown>, path: string, errors: string[]): boolean | undefined {
  const key = lastPathSegment(path);
  if (typeof record[key] !== 'boolean') {
    errors.push(`${path} must be a boolean`);
    return undefined;
  }
  return record[key];
}

function requireLiteral(
  record: Record<string, unknown>,
  path: string,
  expected: string,
  errors: string[],
): void {
  const key = lastPathSegment(path);
  if (record[key] !== expected) {
    errors.push(`${path} must equal '${expected}'`);
  }
}

function requireStringTuple(
  value: unknown,
  path: string,
  length: number,
  errors: string[],
): [string, string] | undefined {
  if (!Array.isArray(value) || value.length !== length || !value.every((entry) => typeof entry === 'string' && entry.length > 0)) {
    errors.push(`${path} must be an array of ${length} non-empty strings`);
    return undefined;
  }
  return value as [string, string];
}

function requireImageSize(value: unknown, path: string, errors: string[]): void {
  const size = asRecord(value, path, errors);
  if (!size) {
    return;
  }
  requirePositiveNumber(size, `${path}.width`, errors);
  requirePositiveNumber(size, `${path}.height`, errors);
}

function requirePositiveNumber(record: Record<string, unknown>, path: string, errors: string[]): number | undefined {
  const value = requireNumber(record, path, errors);
  if (value !== undefined && value <= 0) {
    errors.push(`${path} must be greater than 0`);
  }
  return value;
}

function requireMatrix3x3(value: unknown, path: string, errors: string[]): void {
  requireNestedNumberMatrix(value, path, 3, 3, errors);
}

function requireMatrix3x4(value: unknown, path: string, errors: string[]): void {
  requireNestedNumberMatrix(value, path, 3, 4, errors);
}

function requireNestedNumberMatrix(
  value: unknown,
  path: string,
  rows: number,
  columns: number,
  errors: string[],
): void {
  if (!Array.isArray(value) || value.length !== rows) {
    errors.push(`${path} must be a ${rows}x${columns} numeric matrix`);
    return;
  }
  value.forEach((row, rowIndex) => {
    if (!Array.isArray(row) || row.length !== columns || !row.every((entry) => typeof entry === 'number' && Number.isFinite(entry))) {
      errors.push(`${path}[${rowIndex}] must contain ${columns} finite numbers`);
    }
  });
}

function requireNumberArray(value: unknown, path: string, length: number | undefined, errors: string[]): void {
  if (!Array.isArray(value) || !value.every((entry) => typeof entry === 'number' && Number.isFinite(entry))) {
    errors.push(`${path} must be an array of finite numbers`);
    return;
  }
  if (length !== undefined && value.length !== length) {
    errors.push(`${path} must contain ${length} numbers`);
  }
}

function isSupportedDistortionModel(model: string): boolean {
  return model === 'none' ||
    model === 'opencv_radtan' ||
    model === 'opencv_rational' ||
    model === 'opencv_radial_tangential' ||
    model === 'opencv_fisheye';
}

function lastPathSegment(path: string): string {
  const segments = path.split('.');
  const segment = segments[segments.length - 1];
  if (!segment) {
    throw new Error(`invalid validation path '${path}'`);
  }
  return segment;
}
