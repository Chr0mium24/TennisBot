import * as ort from "onnxruntime-web";
import type { YoloModelArtifactMetadata } from "../../../packages/core/src/index.js";
import { joinArtifactPath } from "./artifacts";
import type {
  BackendYoloBox,
  YoloInferenceBackend,
  YoloInferenceBackendResult,
  YoloInferenceFrame,
} from "./detections";

export type OrtTensor = {
  readonly data: Float32Array | number[] | readonly number[];
  readonly dims: readonly number[];
};

export type OrtSession = {
  readonly inputNames: readonly string[];
  readonly outputNames: readonly string[];
  run(feeds: Record<string, OrtTensor>): Promise<Record<string, OrtTensor>>;
  release?(): Promise<void> | void;
};

export type OrtRuntime = {
  readonly Tensor: new (
    type: "float32",
    data: Float32Array,
    dims: readonly number[],
  ) => OrtTensor;
  readonly InferenceSession: {
    create(modelUrl: string, options?: Record<string, unknown>): Promise<OrtSession>;
  };
};

export type RgbaFrameSource = {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8ClampedArray | readonly number[];
};

export type OnnxYoloBackendOptions = {
  readonly packagePath: string;
  readonly metadata: YoloModelArtifactMetadata;
  readonly runtime?: OrtRuntime;
  readonly confidenceThreshold?: number;
  readonly nmsIouThreshold?: number;
  readonly maxDetections?: number;
};

export type LetterboxTransform = {
  readonly sourceWidth: number;
  readonly sourceHeight: number;
  readonly inputWidth: number;
  readonly inputHeight: number;
  readonly scale: number;
  readonly scaledWidth: number;
  readonly scaledHeight: number;
  readonly padX: number;
  readonly padY: number;
};

const DEFAULT_PAD_VALUE = 114;
const DEFAULT_NMS_IOU_THRESHOLD = 0.5;
const DEFAULT_MAX_DETECTIONS = 10;

export class OnnxYoloInferenceBackend implements YoloInferenceBackend {
  readonly name = "onnxruntime-web-yolo";

  private readonly runtime: OrtRuntime;
  private readonly modelUrl: string;
  private readonly confidenceThreshold: number;
  private readonly nmsIouThreshold: number;
  private readonly maxDetections: number;
  private sessionPromise?: Promise<OrtSession>;
  private session?: OrtSession;

  constructor(private readonly options: OnnxYoloBackendOptions) {
    this.runtime = options.runtime ?? (ort as unknown as OrtRuntime);
    this.modelUrl = joinArtifactPath(options.packagePath, options.metadata.modelPath);
    this.confidenceThreshold =
      options.confidenceThreshold ?? options.metadata.confidenceThreshold;
    this.nmsIouThreshold = options.nmsIouThreshold ?? DEFAULT_NMS_IOU_THRESHOLD;
    this.maxDetections = options.maxDetections ?? DEFAULT_MAX_DETECTIONS;
  }

  async infer(frame: YoloInferenceFrame): Promise<YoloInferenceBackendResult> {
    const blocked = validateMetadata(this.options.metadata);
    if (blocked !== undefined) {
      return { status: "blocked", message: blocked };
    }
    if (frame.source === undefined || frame.source === null) {
      return {
        status: "blocked",
        message: "ONNX YOLO inference requires a readable video, canvas, ImageBitmap, or RGBA frame source.",
      };
    }

    const prepared = readAndPreprocessFrame(frame.source, {
      width: this.options.metadata.inputSizePx.widthPx,
      height: this.options.metadata.inputSizePx.heightPx,
      inputColor: this.options.metadata.inputColor,
    });
    if (!prepared.ok) {
      return { status: "blocked", message: prepared.message };
    }

    let session: OrtSession;
    try {
      session = await this.loadSession();
    } catch (error) {
      return {
        status: "blocked",
        message: `ONNX Runtime Web session could not load ${this.modelUrl}: ${formatUnknownError(error)}`,
      };
    }

    const inputName = session.inputNames[0];
    if (inputName === undefined) {
      return { status: "blocked", message: "ONNX session has no input tensor name." };
    }

    const inputTensor = new this.runtime.Tensor("float32", prepared.tensorData, [
      1,
      3,
      prepared.letterbox.inputHeight,
      prepared.letterbox.inputWidth,
    ]);

    let outputs: Record<string, OrtTensor>;
    try {
      outputs = await session.run({ [inputName]: inputTensor });
    } catch (error) {
      return {
        status: "blocked",
        message: `ONNX Runtime Web inference failed: ${formatUnknownError(error)}`,
      };
    }

    const outputTensor = selectOutputTensor(session, outputs);
    if (outputTensor === undefined) {
      return { status: "blocked", message: "ONNX session did not return an output tensor." };
    }

    const parsed = postprocessYoloOutput(outputTensor, prepared.letterbox, {
      classId: this.options.metadata.classId,
      confidenceThreshold: this.confidenceThreshold,
      nmsIouThreshold: this.nmsIouThreshold,
      maxDetections: this.maxDetections,
    });
    if (!parsed.ok) {
      return { status: "blocked", message: parsed.message };
    }

    return { status: "ok", boxes: parsed.boxes };
  }

  stop(): void {
    const session = this.session;
    this.session = undefined;
    this.sessionPromise = undefined;
    void session?.release?.();
  }

  private async loadSession(): Promise<OrtSession> {
    if (this.session !== undefined) {
      return this.session;
    }
    this.sessionPromise ??= this.runtime.InferenceSession.create(this.modelUrl, {
      executionProviders: ["wasm"],
    });
    this.session = await this.sessionPromise;
    return this.session;
  }
}

export function readAndPreprocessFrame(
  source: unknown,
  options: { width: number; height: number; inputColor: string },
): { ok: true; tensorData: Float32Array; letterbox: LetterboxTransform } | { ok: false; message: string } {
  const image = readRgbaFrameSource(source);
  if (!image.ok) {
    return image;
  }

  const letterbox = createLetterboxTransform({
    sourceWidth: image.frame.width,
    sourceHeight: image.frame.height,
    inputWidth: options.width,
    inputHeight: options.height,
  });
  const data = new Float32Array(3 * options.width * options.height);
  const planeSize = options.width * options.height;
  const pad = DEFAULT_PAD_VALUE / 255;

  data.fill(pad);

  const useBgr = options.inputColor.toUpperCase() === "BGR";
  for (let y = 0; y < letterbox.scaledHeight; y += 1) {
    const sourceY = Math.min(
      image.frame.height - 1,
      Math.floor((y / letterbox.scaledHeight) * image.frame.height),
    );
    for (let x = 0; x < letterbox.scaledWidth; x += 1) {
      const sourceX = Math.min(
        image.frame.width - 1,
        Math.floor((x / letterbox.scaledWidth) * image.frame.width),
      );
      const sourceIndex = (sourceY * image.frame.width + sourceX) * 4;
      const destIndex = (letterbox.padY + y) * options.width + letterbox.padX + x;
      const red = Number(image.frame.data[sourceIndex] ?? 0) / 255;
      const green = Number(image.frame.data[sourceIndex + 1] ?? 0) / 255;
      const blue = Number(image.frame.data[sourceIndex + 2] ?? 0) / 255;

      data[destIndex] = useBgr ? blue : red;
      data[planeSize + destIndex] = green;
      data[planeSize * 2 + destIndex] = useBgr ? red : blue;
    }
  }

  return { ok: true, tensorData: data, letterbox };
}

export function postprocessYoloOutput(
  output: OrtTensor,
  letterbox: LetterboxTransform,
  options: {
    classId: number;
    confidenceThreshold: number;
    nmsIouThreshold: number;
    maxDetections: number;
  },
): { ok: true; boxes: BackendYoloBox[] } | { ok: false; message: string } {
  const data = Array.from(output.data);
  const dims = [...output.dims];
  const rows = extractYoloRows(data, dims);
  if (!rows.ok) {
    return rows;
  }

  const boxes = rows.rows
    .map((row) => decodeYoloRow(row, letterbox, options.classId))
    .filter((box): box is BackendYoloBox => box !== null)
    .filter((box) => box.confidence >= options.confidenceThreshold)
    .sort((left, right) => right.confidence - left.confidence);

  return {
    ok: true,
    boxes: nonMaxSuppression(boxes, options.nmsIouThreshold, options.maxDetections),
  };
}

export function createLetterboxTransform(options: {
  sourceWidth: number;
  sourceHeight: number;
  inputWidth: number;
  inputHeight: number;
}): LetterboxTransform {
  const scale = Math.min(
    options.inputWidth / options.sourceWidth,
    options.inputHeight / options.sourceHeight,
  );
  const scaledWidth = Math.round(options.sourceWidth * scale);
  const scaledHeight = Math.round(options.sourceHeight * scale);
  return {
    sourceWidth: options.sourceWidth,
    sourceHeight: options.sourceHeight,
    inputWidth: options.inputWidth,
    inputHeight: options.inputHeight,
    scale,
    scaledWidth,
    scaledHeight,
    padX: Math.floor((options.inputWidth - scaledWidth) / 2),
    padY: Math.floor((options.inputHeight - scaledHeight) / 2),
  };
}

function validateMetadata(metadata: YoloModelArtifactMetadata): string | undefined {
  if (metadata.modelRuntime !== "onnxruntime" && !metadata.modelPath.endsWith(".onnx")) {
    return `YOLO artifact selected model '${metadata.selectedModel}' is not ONNX-compatible: runtime=${metadata.modelRuntime}, path=${metadata.modelPath}`;
  }
  if (metadata.classId !== 0 || metadata.labels[0] !== "tennis_ball") {
    return "YOLO artifact must expose class 0 as tennis_ball for Live3D runtime detections.";
  }
  return undefined;
}

function selectOutputTensor(
  session: OrtSession,
  outputs: Record<string, OrtTensor>,
): OrtTensor | undefined {
  for (const name of session.outputNames) {
    const tensor = outputs[name];
    if (tensor !== undefined) {
      return tensor;
    }
  }
  return Object.values(outputs)[0];
}

function readRgbaFrameSource(
  source: unknown,
): { ok: true; frame: RgbaFrameSource } | { ok: false; message: string } {
  if (isRgbaFrameSource(source)) {
    return { ok: true, frame: source };
  }

  if (typeof HTMLCanvasElement !== "undefined" && source instanceof HTMLCanvasElement) {
    const context = source.getContext("2d", { willReadFrequently: true });
    if (context === null) {
      return { ok: false, message: "Canvas 2D context is unavailable for YOLO preprocessing." };
    }
    return {
      ok: true,
      frame: context.getImageData(0, 0, source.width, source.height),
    };
  }

  const dimensions = getDrawableDimensions(source);
  if (dimensions === null) {
    return {
      ok: false,
      message: "Frame source is not a readable video, canvas, ImageBitmap, or RGBA frame source.",
    };
  }

  const canvas = createReadbackCanvas(dimensions.width, dimensions.height);
  if (canvas === null) {
    return { ok: false, message: "Browser cannot create a canvas for YOLO frame readback." };
  }
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (context === null) {
    return { ok: false, message: "Canvas 2D context is unavailable for YOLO frame readback." };
  }

  context.drawImage(source as CanvasImageSource, 0, 0, dimensions.width, dimensions.height);
  return {
    ok: true,
    frame: context.getImageData(0, 0, dimensions.width, dimensions.height),
  };
}

function isRgbaFrameSource(source: unknown): source is RgbaFrameSource {
  if (typeof source !== "object" || source === null) {
    return false;
  }
  const value = source as Partial<RgbaFrameSource>;
  return (
    typeof value.width === "number" &&
    typeof value.height === "number" &&
    value.width > 0 &&
    value.height > 0 &&
    (Array.isArray(value.data) || value.data instanceof Uint8ClampedArray)
  );
}

function getDrawableDimensions(source: unknown): { width: number; height: number } | null {
  if (typeof HTMLVideoElement !== "undefined" && source instanceof HTMLVideoElement) {
    const width = source.videoWidth || source.clientWidth;
    const height = source.videoHeight || source.clientHeight;
    return width > 0 && height > 0 ? { width, height } : null;
  }
  if (typeof ImageBitmap !== "undefined" && source instanceof ImageBitmap) {
    return source.width > 0 && source.height > 0
      ? { width: source.width, height: source.height }
      : null;
  }
  return null;
}

function createReadbackCanvas(
  width: number,
  height: number,
): (HTMLCanvasElement | OffscreenCanvas) & {
  getContext(
    contextId: "2d",
    options?: CanvasRenderingContext2DSettings,
  ): CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D | null;
} | null {
  if (typeof OffscreenCanvas !== "undefined") {
    return new OffscreenCanvas(width, height);
  }
  if (typeof document !== "undefined") {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
  }
  return null;
}

function extractYoloRows(
  data: number[],
  dims: number[],
): { ok: true; rows: number[][] } | { ok: false; message: string } {
  if (dims.length === 2 && dims[1] >= 5) {
    return { ok: true, rows: rowsFromFlat(data, dims[0], dims[1]) };
  }
  if (dims.length === 3 && dims[0] === 1 && dims[2] >= 5) {
    return { ok: true, rows: rowsFromFlat(data, dims[1], dims[2]) };
  }
  if (dims.length === 3 && dims[0] === 1 && dims[1] >= 5) {
    const channels = dims[1];
    const count = dims[2];
    const rows: number[][] = [];
    for (let boxIndex = 0; boxIndex < count; boxIndex += 1) {
      const row: number[] = [];
      for (let channel = 0; channel < channels; channel += 1) {
        row.push(data[channel * count + boxIndex] ?? 0);
      }
      rows.push(row);
    }
    return { ok: true, rows };
  }
  return {
    ok: false,
    message: `Unsupported YOLO ONNX output shape [${dims.join(", ")}]. Expected [N,5+], [1,N,5+], or [1,5+,N].`,
  };
}

function rowsFromFlat(data: number[], rowCount: number, rowWidth: number): number[][] {
  const rows: number[][] = [];
  for (let rowIndex = 0; rowIndex < rowCount; rowIndex += 1) {
    const start = rowIndex * rowWidth;
    rows.push(data.slice(start, start + rowWidth));
  }
  return rows;
}

function decodeYoloRow(
  row: number[],
  letterbox: LetterboxTransform,
  classId: number,
): BackendYoloBox | null {
  if (row.length < 5) {
    return null;
  }

  const [xCenter, yCenter, width, height] = row;
  const confidence = row.length === 5 ? row[4] : Math.max(row[4] ?? 0, row[5] ?? 0);
  if (![xCenter, yCenter, width, height, confidence].every(Number.isFinite)) {
    return null;
  }

  const xMin = (xCenter - width / 2 - letterbox.padX) / letterbox.scale;
  const yMin = (yCenter - height / 2 - letterbox.padY) / letterbox.scale;
  const boxWidth = width / letterbox.scale;
  const boxHeight = height / letterbox.scale;

  return {
    classId,
    label: "tennis_ball",
    confidence,
    xPx: clamp(xMin, 0, letterbox.sourceWidth),
    yPx: clamp(yMin, 0, letterbox.sourceHeight),
    widthPx: clamp(boxWidth, 0, letterbox.sourceWidth),
    heightPx: clamp(boxHeight, 0, letterbox.sourceHeight),
  };
}

function nonMaxSuppression(
  boxes: BackendYoloBox[],
  threshold: number,
  maxDetections: number,
): BackendYoloBox[] {
  const kept: BackendYoloBox[] = [];
  for (const box of boxes) {
    if (kept.every((selected) => intersectionOverUnion(box, selected) <= threshold)) {
      kept.push(box);
    }
    if (kept.length >= maxDetections) {
      break;
    }
  }
  return kept;
}

function intersectionOverUnion(left: BackendYoloBox, right: BackendYoloBox): number {
  const leftX2 = left.xPx + left.widthPx;
  const leftY2 = left.yPx + left.heightPx;
  const rightX2 = right.xPx + right.widthPx;
  const rightY2 = right.yPx + right.heightPx;
  const x1 = Math.max(left.xPx, right.xPx);
  const y1 = Math.max(left.yPx, right.yPx);
  const x2 = Math.min(leftX2, rightX2);
  const y2 = Math.min(leftY2, rightY2);
  const intersection = Math.max(0, x2 - x1) * Math.max(0, y2 - y1);
  const union = left.widthPx * left.heightPx + right.widthPx * right.heightPx - intersection;
  return union <= 0 ? 0 : intersection / union;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
