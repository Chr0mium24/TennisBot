import { describe, expect, test } from "bun:test";
import {
  joinArtifactPath,
  loadStereoCalibrationArtifactStatus,
  loadYoloArtifactStatus,
  type JsonReader,
  type JsonReadResult,
} from "./artifacts";

describe("Live3D artifact adapter", () => {
  test("loads valid YOLO and stereo packages from an in-memory reader", async () => {
    const reader = new MemoryJsonReader({
      "/artifacts/models/tennis_ball_yolo/package.json": validYoloBundle().packageJson,
      "/artifacts/models/tennis_ball_yolo/labels.json": validYoloBundle().labelsJson,
      "/artifacts/models/tennis_ball_yolo/preprocessing.json": validYoloBundle().preprocessingJson,
      "/artifacts/models/tennis_ball_yolo/postprocessing.json": validYoloBundle().postprocessingJson,
      "/artifacts/calibration/stereo_cam1_cam2/package.json": validStereoBundle().packageJson,
      "/artifacts/calibration/stereo_cam1_cam2/cam1.json": validStereoBundle().cam1Json,
      "/artifacts/calibration/stereo_cam1_cam2/cam2.json": validStereoBundle().cam2Json,
      "/artifacts/calibration/stereo_cam1_cam2/stereo.json": validStereoBundle().stereoJson,
      "/artifacts/calibration/stereo_cam1_cam2/rectification.json": validStereoBundle().rectificationJson,
      "/artifacts/calibration/stereo_cam1_cam2/verification.json": validStereoBundle().verificationJson,
    });

    const yoloStatus = await loadYoloArtifactStatus(reader, "/artifacts/models/tennis_ball_yolo");
    const stereoStatus = await loadStereoCalibrationArtifactStatus(
      reader,
      "/artifacts/calibration/stereo_cam1_cam2",
    );

    expect(yoloStatus.status).toBe("loaded");
    if (yoloStatus.status === "loaded") {
      expect(yoloStatus.value.packageName).toBe("tennis_ball_yolo");
      expect(yoloStatus.value.selectedModel).toBe("onnx");
      expect(yoloStatus.value.modelPath).toBe("model.onnx");
      expect(yoloStatus.value.boxFormat).toBe("xyxy_pixels");
      expect(yoloStatus.value.confidenceThreshold).toBe(0.05);
      expect(yoloStatus.value.modelChecks).toContainEqual({
        kind: "sha256",
        path: "model.onnx",
        expected: "abc123",
        status: "pending",
      });
    }

    expect(stereoStatus.status).toBe("loaded");
    if (stereoStatus.status === "loaded") {
      expect(stereoStatus.value.left.cameraId).toBe("cam1");
      expect(stereoStatus.value.right.cameraId).toBe("cam2");
      expect(stereoStatus.value.extrinsics.baselineMeters).toBe(0.12);
    }
  });

  test("missing YOLO labels.json returns blocked status with the missing file", async () => {
    const bundle = validYoloBundle();
    const reader = new MemoryJsonReader({
      "/model/package.json": bundle.packageJson,
      "/model/preprocessing.json": bundle.preprocessingJson,
      "/model/postprocessing.json": bundle.postprocessingJson,
    });

    const status = await loadYoloArtifactStatus(reader, "/model");

    expect(status.status).toBe("blocked");
    if (status.status === "blocked") {
      expect(status.errors.join("\n")).toContain("labels.json");
      expect(status.errors.join("\n")).toContain("missing");
    }
  });

  test("invalid YOLO class 0 returns blocked status", async () => {
    const bundle = validYoloBundle();
    bundle.labelsJson = {
      ...bundle.labelsJson,
      classes: [{ id: 0, name: "not_tennis_ball" }],
    };
    const reader = yoloReader("/model", bundle);

    const status = await loadYoloArtifactStatus(reader, "/model");

    expect(status.status).toBe("blocked");
    if (status.status === "blocked") {
      expect(status.errors).toContain("labels.json.classes must include class id 0 named tennis_ball");
    }
  });

  test("missing optional calibration verification.json warns but still loads accepted package", async () => {
    const bundle = validStereoBundle();
    const reader = stereoReader("/calibration", bundle, { includeVerification: false });

    const status = await loadStereoCalibrationArtifactStatus(reader, "/calibration");

    expect(status.status).toBe("loaded");
    if (status.status === "loaded") {
      expect(status.value.left.cameraId).toBe("cam1");
      expect(status.warnings.join("\n")).toContain("verification.json");
      expect(status.warnings.join("\n")).toContain("package.json.quality.accepted");
    }
  });

  test("rejected calibration package returns blocked status", async () => {
    const bundle = validStereoBundle();
    bundle.packageJson = {
      ...bundle.packageJson,
      quality: { ...bundle.packageJson.quality, accepted: false },
    };
    bundle.verificationJson = {
      ...bundle.verificationJson,
      accepted: false,
      rectification: { ...bundle.verificationJson.rectification, accepted: false },
    };
    const reader = stereoReader("/calibration", bundle);

    const status = await loadStereoCalibrationArtifactStatus(reader, "/calibration");

    expect(status.status).toBe("blocked");
    if (status.status === "blocked") {
      expect(status.errors).toContain("package.json.quality.accepted must be true for runtime loading");
      expect(status.errors).toContain("verification.json.accepted must be true for runtime loading");
      expect(status.errors).toContain(
        "verification.json.rectification.accepted must be true for runtime loading",
      );
    }
  });
});

class MemoryJsonReader implements JsonReader {
  constructor(private readonly files: Record<string, unknown>) {}

  async readJson(path: string): Promise<JsonReadResult> {
    if (!(path in this.files)) {
      return { ok: false, message: `${path} missing` };
    }

    return { ok: true, value: this.files[path] };
  }
}

function yoloReader(
  packagePath: string,
  bundle: ReturnType<typeof validYoloBundle>,
): MemoryJsonReader {
  return new MemoryJsonReader({
    [joinArtifactPath(packagePath, "package.json")]: bundle.packageJson,
    [joinArtifactPath(packagePath, "labels.json")]: bundle.labelsJson,
    [joinArtifactPath(packagePath, "preprocessing.json")]: bundle.preprocessingJson,
    [joinArtifactPath(packagePath, "postprocessing.json")]: bundle.postprocessingJson,
  });
}

function stereoReader(
  packagePath: string,
  bundle: ReturnType<typeof validStereoBundle>,
  options: { includeVerification: boolean } = { includeVerification: true },
): MemoryJsonReader {
  return new MemoryJsonReader({
    [joinArtifactPath(packagePath, "package.json")]: bundle.packageJson,
    [joinArtifactPath(packagePath, "cam1.json")]: bundle.cam1Json,
    [joinArtifactPath(packagePath, "cam2.json")]: bundle.cam2Json,
    [joinArtifactPath(packagePath, "stereo.json")]: bundle.stereoJson,
    [joinArtifactPath(packagePath, "rectification.json")]: bundle.rectificationJson,
    ...(options.includeVerification
      ? { [joinArtifactPath(packagePath, "verification.json")]: bundle.verificationJson }
      : {}),
  });
}

function validYoloBundle() {
  return {
    packageJson: {
      name: "tennis_ball_yolo",
      version: "0.1.0",
      contract: "tennisbot.yolo-model-package",
      contract_version: "0.1.0",
      created_at: "2026-06-28T00:00:00Z",
      models: {
        onnx: {
          path: "model.onnx",
          sha256: "abc123",
          bytes: 1024,
          runtime: "onnxruntime",
        },
      },
      default_model: "onnx",
      labels: "labels.json",
      preprocessing: "preprocessing.json",
      postprocessing: "postprocessing.json",
    },
    labelsJson: {
      classes: [{ id: 0, name: "tennis_ball" }],
      format: "YOLO detect normalized xywh",
    },
    preprocessingJson: {
      input_color: "RGB",
      input_size: { width: 1280, height: 1280 },
      resize: { mode: "letterbox", preserve_aspect_ratio: true, stride: 32 },
      normalization: { scale: 1 / 255, mean: [0, 0, 0], std: [1, 1, 1] },
    },
    postprocessingJson: {
      task: "single-class tennis ball detection",
      box_format: "xyxy_pixels",
      source_box_format: "YOLO normalized xywh",
      class_id: 0,
      confidence_threshold: 0.05,
      nms_iou_threshold: 0.5,
      max_detections: 10,
      runtime_output: "detections",
    },
  };
}

function validStereoBundle() {
  return {
    packageJson: {
      schema_version: "calibration.stereo.v1",
      package_type: "stereo_camera_calibration",
      camera_ids: ["cam1", "cam2"],
      created_at: "2026-06-28T00:00:00Z",
      source_session: "captures/local/stereo_cam1_cam2_session",
      files: {
        cam1: "cam1.json",
        cam2: "cam2.json",
        stereo: "stereo.json",
        rectification: "rectification.json",
      },
      quality: {
        accepted: true,
        stereo_rms_reprojection_px: 0.42,
        accepted_pair_count: 28,
        total_pair_count: 32,
      },
    },
    cam1Json: cameraJson("cam1"),
    cam2Json: cameraJson("cam2"),
    stereoJson: {
      schema_version: "calibration.stereo_extrinsics.v1",
      left_camera_id: "cam1",
      right_camera_id: "cam2",
      rotation_left_to_right: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
      translation_left_to_right_m: [0.12, 0, 0],
      baseline_m: 0.12,
    },
    rectificationJson: {
      schema_version: "calibration.rectification.v1",
      left_camera_id: "cam1",
      right_camera_id: "cam2",
      image_size: { width: 1920, height: 1080 },
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
      schema_version: "calibration.stereo_verification.v1",
      accepted: true,
      checks: [{ name: "stereo_rms_reprojection_px", passed: true, value: 0.42, threshold: 0.75 }],
      rectification: { epipolar_error_px: 0.3, accepted: true },
    },
  };
}

function cameraJson(cameraId: "cam1" | "cam2") {
  return {
    schema_version: "calibration.camera_intrinsics.v1",
    camera_id: cameraId,
    image_size: { width: 1920, height: 1080 },
    camera_matrix: [
      [1200, 0, 960],
      [0, 1200, 540],
      [0, 0, 1],
    ],
    distortion_model: "opencv_rational",
    distortion_coefficients: [0, 0, 0, 0, 0, 0, 0, 0],
  };
}
