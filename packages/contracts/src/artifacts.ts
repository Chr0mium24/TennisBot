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
