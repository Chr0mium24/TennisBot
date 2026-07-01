import { describe, expect, test } from 'bun:test';
import type {
  CameraIntrinsicsArtifactJson,
  RectificationArtifactJson,
  StereoCalibrationPackageJson,
  StereoExtrinsicsArtifactJson,
  StereoVerificationArtifactJson,
  YoloLabelsJson,
  YoloPackageJson,
  YoloPostprocessingJson,
  YoloPreprocessingJson,
} from '../../contracts/src/index.js';
import {
  loadStereoCalibrationArtifact,
  loadYoloModelArtifactMetadata,
  matrix3x3FromArtifact,
  matrix3x4FromArtifact,
} from './index.js';

describe('artifact loaders', () => {
  test('validates and converts valid YOLO package metadata', () => {
    const result = loadYoloModelArtifactMetadata(validYoloBundle());

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toMatchObject({
        packageName: 'tennis_ball_yolo',
        selectedModel: 'onnx',
        modelPath: 'model.onnx',
        modelRuntime: 'onnxruntime',
        confidenceThreshold: 0.05,
        classId: 0,
        labels: ['tennis_ball'],
        inputColor: 'RGB',
        boxFormat: 'xyxy_pixels',
        sourceBoxFormat: 'YOLO normalized xywh',
      });
      expect(result.value.inputSizePx).toEqual({ widthPx: 1280, heightPx: 1280 });
      expect(result.value.modelChecks).toContainEqual({
        kind: 'file-exists',
        path: 'model.onnx',
        status: 'pending',
      });
    }
  });

  test('rejects YOLO package metadata missing class 0 tennis_ball', () => {
    const bundle = validYoloBundle();
    bundle.labelsJson = { classes: [{ id: 1, name: 'tennis_ball' }] };

    const result = loadYoloModelArtifactMetadata(bundle);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('labels.json.classes must include class id 0 named tennis_ball');
    }
  });

  test('rejects malformed YOLO class entries without throwing', () => {
    const bundle = validYoloBundle();
    bundle.labelsJson = { classes: [null] } as unknown as YoloLabelsJson;

    const result = loadYoloModelArtifactMetadata(bundle);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('labels.json.classes[0] must be an object');
      expect(result.errors).toContain('labels.json.classes must include class id 0 named tennis_ball');
    }
  });

  test('rejects YOLO model entries missing checksum metadata', () => {
    const bundle = validYoloBundle();
    bundle.packageJson = {
      ...bundle.packageJson,
      models: {
        onnx: { path: 'model.onnx', runtime: 'onnxruntime' } as unknown as YoloPackageJson['models'][string],
      },
    };

    const result = loadYoloModelArtifactMetadata(bundle);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('package.json.models.onnx.sha256 must be a non-empty string');
      expect(result.errors).toContain('package.json.models.onnx.bytes must be a finite number');
    }
  });

  test('validates and converts accepted stereo calibration package metadata', () => {
    const result = loadStereoCalibrationArtifact(validStereoBundle());

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.left.cameraId).toBe('cam1');
      expect(result.value.right.cameraId).toBe('cam2');
      expect(result.value.left.imageSize).toEqual({ widthPx: 1920, heightPx: 1080 });
      expect(result.value.extrinsics.translationLeftToRightMeters).toEqual({ x: 0.12, y: 0, z: 0 });
      expect(result.value.extrinsics.rmsReprojectionErrorPx).toBe(0.42);
      expect(result.value.rectifiedProjection?.leftProjectionMatrix.values).toEqual([
        1200, 0, 960, 0,
        0, 1200, 540, 0,
        0, 0, 1, 0,
      ]);
      expect(result.value.rectifiedProjection?.leftRectificationMatrix?.values).toEqual([
        1, 0, 0,
        0, 1, 0,
        0, 0, 1,
      ]);
    }
  });

  test('rejects stereo calibration package where quality and verification are not accepted', () => {
    const bundle = validStereoBundle();
    bundle.packageJson = {
      ...bundle.packageJson,
      quality: { ...bundle.packageJson.quality, accepted: false },
    };
    bundle.verificationJson = {
      ...bundle.verificationJson,
      accepted: false,
      rectification: { accepted: false },
    };

    const result = loadStereoCalibrationArtifact(bundle);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('package.json.quality.accepted must be true for runtime loading');
      expect(result.errors).toContain('verification.json.accepted must be true for runtime loading');
      expect(result.errors).toContain('verification.json.rectification.accepted must be true for runtime loading');
    }
  });

  test('rejects rectification camera IDs that do not match the stereo package', () => {
    const bundle = validStereoBundle();
    bundle.rectificationJson = {
      ...bundle.rectificationJson,
      left_camera_id: 'cam3',
    };

    const result = loadStereoCalibrationArtifact(bundle);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.errors).toContain('rectification.json.left_camera_id must match package.json.camera_ids[0]');
      expect(result.errors).toContain('rectification.json.left_camera_id must match stereo.json.left_camera_id');
    }
  });

  test('flattens artifact matrices in row-major order', () => {
    expect(matrix3x3FromArtifact([
      [1, 2, 3],
      [4, 5, 6],
      [7, 8, 9],
    ])).toEqual({
      values: [1, 2, 3, 4, 5, 6, 7, 8, 9],
      storage: 'row-major',
    });

    expect(matrix3x4FromArtifact([
      [1, 2, 3, 4],
      [5, 6, 7, 8],
      [9, 10, 11, 12],
    ])).toEqual({
      values: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
      storage: 'row-major',
    });
  });
});

function validYoloBundle(): {
  packageJson: YoloPackageJson;
  labelsJson: YoloLabelsJson;
  preprocessingJson: YoloPreprocessingJson;
  postprocessingJson: YoloPostprocessingJson;
} {
  return {
    packageJson: {
      name: 'tennis_ball_yolo',
      version: '0.1.0',
      contract: 'tennisbot.yolo-model-package',
      contract_version: '0.1.0',
      created_at: '2026-06-28T00:00:00Z',
      models: {
        onnx: {
          path: 'model.onnx',
          sha256: 'abc123',
          bytes: 1024,
          runtime: 'onnxruntime',
        },
      },
      default_model: 'onnx',
      labels: 'labels.json',
      preprocessing: 'preprocessing.json',
      postprocessing: 'postprocessing.json',
    },
    labelsJson: {
      classes: [{ id: 0, name: 'tennis_ball' }],
      format: 'YOLO detect normalized xywh',
    },
    preprocessingJson: {
      input_color: 'RGB',
      input_size: { width: 1280, height: 1280 },
      resize: { mode: 'letterbox', preserve_aspect_ratio: true, stride: 32 },
      normalization: { scale: 1 / 255, mean: [0, 0, 0], std: [1, 1, 1] },
    },
    postprocessingJson: {
      task: 'single-class tennis ball detection',
      box_format: 'xyxy_pixels',
      source_box_format: 'YOLO normalized xywh',
      class_id: 0,
      confidence_threshold: 0.05,
      nms_iou_threshold: 0.5,
      max_detections: 10,
      runtime_output: 'detections',
    },
  };
}

function validStereoBundle(): {
  packageJson: StereoCalibrationPackageJson;
  cam1Json: CameraIntrinsicsArtifactJson;
  cam2Json: CameraIntrinsicsArtifactJson;
  stereoJson: StereoExtrinsicsArtifactJson;
  rectificationJson: RectificationArtifactJson;
  verificationJson: StereoVerificationArtifactJson;
} {
  return {
    packageJson: {
      schema_version: 'calibration.stereo.v1',
      package_type: 'stereo_camera_calibration',
      camera_ids: ['cam1', 'cam2'],
      created_at: '2026-06-28T00:00:00Z',
      source_session: 'captures/local/stereo_cam1_cam2_session',
      files: {
        cam1: 'cam1.json',
        cam2: 'cam2.json',
        stereo: 'stereo.json',
        rectification: 'rectification.json',
      },
      quality: {
        accepted: true,
        stereo_rms_reprojection_px: 0.42,
        accepted_pair_count: 28,
        total_pair_count: 32,
      },
    },
    cam1Json: cameraJson('cam1'),
    cam2Json: cameraJson('cam2'),
    stereoJson: {
      schema_version: 'calibration.stereo_extrinsics.v1',
      left_camera_id: 'cam1',
      right_camera_id: 'cam2',
      rotation_left_to_right: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      translation_left_to_right_m: [0.12, 0, 0],
      baseline_m: 0.12,
    },
    rectificationJson: {
      schema_version: 'calibration.rectification.v1',
      left_camera_id: 'cam1',
      right_camera_id: 'cam2',
      image_size: { width: 1920, height: 1080 },
      r1: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      r2: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      p1: [
        [1200, 0, 960, 0],
        [0, 1200, 540, 0],
        [0, 0, 1, 0],
      ],
      p2: [
        [1200, 0, 960, -144],
        [0, 1200, 540, 0],
        [0, 0, 1, 0],
      ],
    },
    verificationJson: {
      schema_version: 'calibration.stereo_verification.v1',
      accepted: true,
      checks: [{ name: 'stereo_rms_reprojection_px', passed: true, value: 0.42, threshold: 0.75 }],
      rectification: { epipolar_error_px: 0.3, accepted: true },
    },
  };
}

function cameraJson(cameraId: 'cam1' | 'cam2'): CameraIntrinsicsArtifactJson {
  return {
    schema_version: 'calibration.camera_intrinsics.v1',
    camera_id: cameraId,
    image_size: { width: 1920, height: 1080 },
    camera_matrix: [
      [1200, 0, 960],
      [0, 1200, 540],
      [0, 0, 1],
    ],
    distortion_model: 'opencv_rational',
    distortion_coefficients: [0, 0, 0, 0, 0, 0, 0, 0],
  };
}
