import { describe, expect, test } from "bun:test";
import type { YoloModelArtifactMetadata } from "../../../packages/core/src/index.js";
import type { YoloInferenceFrame } from "./detections";
import {
  OnnxYoloInferenceBackend,
  createLetterboxTransform,
  postprocessYoloOutput,
  readAndPreprocessFrame,
  type OrtRuntime,
  type OrtSession,
  type OrtTensor,
} from "./onnx-yolo";

describe("Live3D ONNX YOLO backend", () => {
  test("letterboxes RGBA frame data into RGB NCHW tensor data", () => {
    const result = readAndPreprocessFrame(
      {
        width: 2,
        height: 1,
        data: new Uint8ClampedArray([
          255, 0, 0, 255,
          0, 255, 0, 255,
        ]),
      },
      { width: 4, height: 4, inputColor: "RGB" },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }

    expect(result.letterbox).toMatchObject({
      sourceWidth: 2,
      sourceHeight: 1,
      inputWidth: 4,
      inputHeight: 4,
      scaledWidth: 4,
      scaledHeight: 2,
      padX: 0,
      padY: 1,
    });
    expect(result.tensorData[4]).toBe(1);
    expect(result.tensorData[5]).toBe(1);
    expect(result.tensorData[16 + 6]).toBe(1);
    expect(result.tensorData[16 + 7]).toBe(1);
    expect(result.tensorData[0]).toBeCloseTo(114 / 255);
  });

  test("postprocesses [1,N,6] YOLO output and applies NMS", () => {
    const letterbox = createLetterboxTransform({
      sourceWidth: 640,
      sourceHeight: 480,
      inputWidth: 640,
      inputHeight: 640,
    });
    const result = postprocessYoloOutput(
      {
        dims: [1, 3, 6],
        data: new Float32Array([
          320, 320, 64, 64, 0.9, 0.9,
          322, 322, 64, 64, 0.8, 0.8,
          100, 120, 20, 20, 0.04, 0.04,
        ]),
      },
      letterbox,
      {
        classId: 0,
        confidenceThreshold: 0.05,
        nmsIouThreshold: 0.5,
        maxDetections: 10,
      },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }

    expect(result.boxes).toHaveLength(1);
    expect(result.boxes[0]).toMatchObject({
      classId: 0,
      label: "tennis_ball",
      confidence: expect.closeTo(0.9, 5),
      xPx: 288,
      yPx: 208,
      widthPx: 64,
      heightPx: 64,
    });
  });

  test("postprocesses transposed [1,6,N] YOLO output", () => {
    const result = postprocessYoloOutput(
      {
        dims: [1, 6, 2],
        data: new Float32Array([
          50, 150,
          60, 160,
          20, 30,
          10, 40,
          0.3, 0.7,
          0.3, 0.7,
        ]),
      },
      createLetterboxTransform({
        sourceWidth: 200,
        sourceHeight: 200,
        inputWidth: 200,
        inputHeight: 200,
      }),
      {
        classId: 0,
        confidenceThreshold: 0.5,
        nmsIouThreshold: 0.5,
        maxDetections: 10,
      },
    );

    expect(result.ok).toBe(true);
    if (!result.ok) {
      return;
    }
    expect(result.boxes).toHaveLength(1);
    expect(result.boxes[0].xPx).toBe(135);
    expect(result.boxes[0].yPx).toBe(140);
  });

  test("returns blocked status for unsupported runtime before loading a session", async () => {
    const backend = new OnnxYoloInferenceBackend({
      packagePath: "/artifacts/models/tennis_ball_yolo",
      metadata: { ...metadata(), modelRuntime: "rknn", modelPath: "model.rknn" },
      runtime: fakeRuntime(sessionWithOutput([1, 0, 6], [])),
    });

    const result = await backend.infer(frame());

    expect(result.status).toBe("blocked");
    if (result.status === "blocked") {
      expect(result.message).toContain("not ONNX-compatible");
    }
  });

  test("uses injected ORT runtime and reports unsupported output shape as blocked", async () => {
    const backend = new OnnxYoloInferenceBackend({
      packagePath: "/artifacts/models/tennis_ball_yolo",
      metadata: metadata(),
      runtime: fakeRuntime(sessionWithOutput([1, 2, 3, 4], [0])),
    });

    const result = await backend.infer(frame());

    expect(result.status).toBe("blocked");
    if (result.status === "blocked") {
      expect(result.message).toContain("Unsupported YOLO ONNX output shape");
    }
  });

  test("runs injected ORT session and returns source-frame boxes", async () => {
    const session = sessionWithOutput(
      [1, 1, 6],
      [160, 160, 32, 32, 0.95, 0.95],
    );
    const runtime = fakeRuntime(session);
    const backend = new OnnxYoloInferenceBackend({
      packagePath: "/artifacts/models/tennis_ball_yolo",
      metadata: metadata(),
      runtime,
    });

    const result = await backend.infer(frame());

    expect(runtime.createdModelUrls).toEqual([
      "/artifacts/models/tennis_ball_yolo/model.onnx",
    ]);
    expect(session.lastFeedDims).toEqual([1, 3, 320, 320]);
    expect(result.status).toBe("ok");
    if (result.status === "ok") {
      expect(result.boxes).toHaveLength(1);
      expect(result.boxes[0].confidence).toBeCloseTo(0.95);
      expect(result.boxes[0].xPx).toBe(144);
      expect(result.boxes[0].yPx).toBe(104);
    }
  });
});

function frame(): YoloInferenceFrame {
  return {
    side: "left",
    cameraId: "cam-left",
    frameId: "frame-1",
    timestampUnixMs: 1_770_000_000_000,
    imageSize: { widthPx: 320, heightPx: 240 },
    source: {
      width: 320,
      height: 240,
      data: new Uint8ClampedArray(320 * 240 * 4),
    },
  };
}

function metadata(): YoloModelArtifactMetadata {
  return {
    packageName: "tennis_ball_yolo",
    packageVersion: "0.1.0",
    contractVersion: "0.1.0",
    labels: ["tennis_ball"],
    inputSizePx: { widthPx: 320, heightPx: 320 },
    inputColor: "RGB",
    confidenceThreshold: 0.05,
    classId: 0,
    modelPath: "model.onnx",
    modelRuntime: "onnxruntime",
    selectedModel: "onnx",
    modelChecks: [],
  };
}

function fakeRuntime(session: FakeSession): OrtRuntime & { createdModelUrls: string[] } {
  const createdModelUrls: string[] = [];
  return {
    createdModelUrls,
    Tensor: class FakeTensor implements OrtTensor {
      constructor(
        readonly type: "float32",
        readonly data: Float32Array,
        readonly dims: readonly number[],
      ) {}
    },
    InferenceSession: {
      async create(modelUrl: string): Promise<OrtSession> {
        createdModelUrls.push(modelUrl);
        return session;
      },
    },
  };
}

type FakeSession = OrtSession & { lastFeedDims?: readonly number[] };

function sessionWithOutput(dims: number[], data: number[]): FakeSession {
  return {
    inputNames: ["images"],
    outputNames: ["output0"],
    async run(feeds): Promise<Record<string, OrtTensor>> {
      this.lastFeedDims = feeds.images.dims;
      return {
        output0: {
          dims,
          data: new Float32Array(data),
        },
      };
    },
  };
}
