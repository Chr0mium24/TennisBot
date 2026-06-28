import type {
  CalibrationArtifactReference,
  StereoCalibration,
  YoloModelArtifactReference,
} from '../../contracts/src/index.js';

export interface CalibrationArtifactLoader {
  loadStereoCalibration(reference: CalibrationArtifactReference): Promise<StereoCalibration>;
}

export interface YoloModelArtifactMetadata {
  labels: string[];
  inputSizePx: number;
  confidenceThreshold: number;
  modelPath: string;
}

export interface YoloModelArtifactLoader {
  loadYoloModelMetadata(reference: YoloModelArtifactReference): Promise<YoloModelArtifactMetadata>;
}

export interface RuntimeArtifactLoaders extends CalibrationArtifactLoader, YoloModelArtifactLoader {}
