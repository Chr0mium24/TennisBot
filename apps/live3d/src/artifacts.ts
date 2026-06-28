import type { StereoCalibration } from "../../../packages/contracts/src/index.js";
import {
  loadStereoCalibrationArtifact,
  loadYoloModelArtifactMetadata,
  type YoloModelArtifactMetadata,
} from "../../../packages/core/src/index.js";

export interface JsonReader {
  readJson(path: string): Promise<JsonReadResult>;
}

export type JsonReadResult =
  | { ok: true; value: unknown }
  | { ok: false; message: string };

export type ArtifactLoadStatus<T> =
  | {
      status: "loaded";
      packagePath: string;
      value: T;
      warnings: string[];
    }
  | {
      status: "blocked";
      packagePath: string;
      message: string;
      errors: string[];
      warnings: string[];
    };

export type YoloArtifactLoadStatus = ArtifactLoadStatus<YoloModelArtifactMetadata>;
export type StereoCalibrationArtifactLoadStatus = ArtifactLoadStatus<StereoCalibration>;

const YOLO_PACKAGE_FILES = [
  "package.json",
  "labels.json",
  "preprocessing.json",
  "postprocessing.json",
] as const;

const STEREO_REQUIRED_FILES = [
  "package.json",
  "cam1.json",
  "cam2.json",
  "stereo.json",
  "rectification.json",
] as const;

export class BrowserFetchJsonReader implements JsonReader {
  async readJson(path: string): Promise<JsonReadResult> {
    try {
      const response = await fetch(path, { headers: { accept: "application/json" } });
      if (!response.ok) {
        return {
          ok: false,
          message: `${path} returned HTTP ${response.status}`,
        };
      }
      return { ok: true, value: await response.json() };
    } catch (error) {
      return {
        ok: false,
        message: `${path} could not be read: ${formatUnknownError(error)}`,
      };
    }
  }
}

export async function loadYoloArtifactStatus(
  reader: JsonReader,
  packagePath: string,
): Promise<YoloArtifactLoadStatus> {
  const files = await readRequiredFiles(reader, packagePath, YOLO_PACKAGE_FILES);
  if (!files.ok) {
    return blocked(packagePath, "YOLO artifact package is blocked.", files.errors);
  }

  const result = loadYoloModelArtifactMetadata({
    packageJson: files.values["package.json"],
    labelsJson: files.values["labels.json"],
    preprocessingJson: files.values["preprocessing.json"],
    postprocessingJson: files.values["postprocessing.json"],
  });

  if (!result.ok) {
    return blocked(packagePath, "YOLO artifact validation failed.", result.errors, result.warnings);
  }

  return {
    status: "loaded",
    packagePath,
    value: result.value,
    warnings: result.warnings,
  };
}

export async function loadStereoCalibrationArtifactStatus(
  reader: JsonReader,
  packagePath: string,
): Promise<StereoCalibrationArtifactLoadStatus> {
  const files = await readRequiredFiles(reader, packagePath, STEREO_REQUIRED_FILES);
  if (!files.ok) {
    return blocked(packagePath, "Stereo calibration artifact package is blocked.", files.errors);
  }

  const verificationJson = await reader.readJson(joinArtifactPath(packagePath, "verification.json"));
  const result = loadStereoCalibrationArtifact({
    packageJson: files.values["package.json"],
    cam1Json: files.values["cam1.json"],
    cam2Json: files.values["cam2.json"],
    stereoJson: files.values["stereo.json"],
    rectificationJson: files.values["rectification.json"],
    verificationJson: verificationJson.ok ? verificationJson.value : undefined,
  });

  const warnings = verificationJson.ok
    ? result.warnings
    : [`verification.json could not be loaded: ${verificationJson.message}`, ...result.warnings];

  if (!result.ok) {
    return blocked(packagePath, "Stereo calibration artifact validation failed.", result.errors, warnings);
  }

  return {
    status: "loaded",
    packagePath,
    value: result.value,
    warnings,
  };
}

export function joinArtifactPath(packagePath: string, filename: string): string {
  return `${packagePath.replace(/\/+$/, "")}/${filename}`;
}

function blocked<T>(
  packagePath: string,
  message: string,
  errors: string[],
  warnings: string[] = [],
): ArtifactLoadStatus<T> {
  return {
    status: "blocked",
    packagePath,
    message,
    errors,
    warnings,
  };
}

async function readRequiredFiles<TFile extends string>(
  reader: JsonReader,
  packagePath: string,
  filenames: readonly TFile[],
): Promise<{ ok: true; values: Record<TFile, unknown> } | { ok: false; errors: string[] }> {
  const values = {} as Record<TFile, unknown>;
  const errors: string[] = [];

  for (const filename of filenames) {
    const path = joinArtifactPath(packagePath, filename);
    const result = await reader.readJson(path);
    if (result.ok) {
      values[filename] = result.value;
    } else {
      errors.push(`${filename}: ${result.message}`);
    }
  }

  return errors.length === 0 ? { ok: true, values } : { ok: false, errors };
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
