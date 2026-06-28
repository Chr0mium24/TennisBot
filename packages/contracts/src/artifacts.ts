export interface ArtifactReference {
  artifactId: string;
  path: string;
  version: string;
}

export interface CalibrationArtifactReference extends ArtifactReference {
  kind: 'stereo-calibration';
}

export interface YoloModelArtifactReference extends ArtifactReference {
  kind: 'yolo-model';
  labelsPath?: string;
  modelPath?: string;
}

export type ArtifactMatrix3x3Json = [
  [number, number, number],
  [number, number, number],
  [number, number, number],
];

export type ArtifactMatrix3x4Json = [
  [number, number, number, number],
  [number, number, number, number],
  [number, number, number, number],
];

export type ArtifactMatrix4x4Json = [
  [number, number, number, number],
  [number, number, number, number],
  [number, number, number, number],
  [number, number, number, number],
];

export interface ArtifactImageSizeJson {
  width: number;
  height: number;
}

export interface YoloPackageModelEntryJson {
  path: string;
  sha256?: string;
  bytes?: number;
  runtime: string;
}

export interface YoloPackageJson {
  name: string;
  version: string;
  contract: 'tennisbot.yolo-model-package';
  contract_version: string;
  created_at: string;
  producer?: {
    tool?: string;
    source?: string;
  };
  models: Record<string, YoloPackageModelEntryJson>;
  default_model: string;
  labels: string;
  preprocessing: string;
  postprocessing: string;
  evaluation?: {
    report?: string;
    metrics?: string;
  };
}

export interface YoloLabelClassJson {
  id: number;
  name: string;
}

export interface YoloLabelsJson {
  classes: YoloLabelClassJson[];
  format?: string;
}

export interface YoloPreprocessingJson {
  input_color: 'RGB' | 'BGR' | string;
  input_size: ArtifactImageSizeJson;
  resize?: {
    mode: string;
    preserve_aspect_ratio?: boolean;
    stride?: number;
  };
  normalization?: {
    scale: number;
    mean: number[];
    std: number[];
  };
}

export interface YoloPostprocessingJson {
  task?: string;
  box_format: string;
  source_box_format?: string;
  class_id: number;
  confidence_threshold: number;
  nms_iou_threshold?: number;
  max_detections?: number;
  runtime_output?: string;
}

export interface YoloModelArtifactJsonBundle {
  packageJson: unknown;
  labelsJson: unknown;
  preprocessingJson: unknown;
  postprocessingJson: unknown;
}

export interface CalibrationPackageQualityJson {
  accepted: boolean;
  stereo_rms_reprojection_px?: number;
  accepted_pair_count?: number;
  total_pair_count?: number;
}

export interface StereoCalibrationPackageJson {
  schema_version: 'calibration.stereo.v1';
  package_type: 'stereo_camera_calibration';
  camera_ids: [string, string];
  created_at: string;
  source_session: string;
  mono_sources?: Record<string, string>;
  target?: Record<string, unknown>;
  files: {
    cam1: string;
    cam2: string;
    stereo: string;
    rectification: string;
    opencv_yaml?: string;
    verification?: string;
    summary?: string;
  };
  quality: CalibrationPackageQualityJson;
}

export interface CameraIntrinsicsArtifactJson {
  schema_version: 'calibration.camera_intrinsics.v1';
  camera_id: string;
  image_size: ArtifactImageSizeJson;
  camera_matrix: ArtifactMatrix3x3Json;
  distortion_model: string;
  distortion_coefficients: number[];
  new_camera_matrix?: ArtifactMatrix3x3Json;
  roi?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
}

export interface StereoExtrinsicsArtifactJson {
  schema_version: 'calibration.stereo_extrinsics.v1';
  left_camera_id: string;
  right_camera_id: string;
  rotation_left_to_right: ArtifactMatrix3x3Json;
  translation_left_to_right_m: [number, number, number];
  essential_matrix?: ArtifactMatrix3x3Json;
  fundamental_matrix?: ArtifactMatrix3x3Json;
  baseline_m?: number;
}

export interface RectificationArtifactJson {
  schema_version: 'calibration.rectification.v1';
  left_camera_id: string;
  right_camera_id: string;
  image_size: ArtifactImageSizeJson;
  r1?: ArtifactMatrix3x3Json;
  r2?: ArtifactMatrix3x3Json;
  p1: ArtifactMatrix3x4Json;
  p2: ArtifactMatrix3x4Json;
  q?: ArtifactMatrix4x4Json;
}

export interface StereoVerificationArtifactJson {
  schema_version: 'calibration.stereo_verification.v1';
  accepted: boolean;
  checks?: Array<{
    name: string;
    passed: boolean;
    value?: number;
    threshold?: number;
    minimum?: number;
    maximum?: number;
  }>;
  rectification?: {
    epipolar_error_px?: number;
    accepted?: boolean;
  };
}

export interface StereoCalibrationArtifactJsonBundle {
  packageJson: unknown;
  cam1Json: unknown;
  cam2Json: unknown;
  stereoJson: unknown;
  rectificationJson: unknown;
  verificationJson?: unknown;
}
