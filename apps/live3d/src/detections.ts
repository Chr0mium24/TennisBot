import type { ImageSize, YoloDetection2D } from "../../../packages/contracts/src/index.js";
import type { CameraSide } from "./cameras";

export type YoloInferenceStatusCode =
  | "not-started"
  | "running"
  | "updated"
  | "backend-blocked"
  | "invalid-output";

export type YoloInferenceRuntimeStatus = {
  side: CameraSide;
  state: "idle" | "running" | "ready" | "blocked";
  code: YoloInferenceStatusCode;
  label: string;
  detail: string;
  frameId?: string;
  timestampUnixMs?: number;
  imageSize?: ImageSize;
  detectionCount: number;
  detections: YoloDetection2D[];
  warnings: string[];
};

export type StereoYoloInferenceRuntimeStatus = {
  left: YoloInferenceRuntimeStatus;
  right: YoloInferenceRuntimeStatus;
};

export type YoloInferenceFrame = {
  side: CameraSide;
  cameraId: string;
  frameId: string;
  timestampUnixMs: number;
  imageSize: ImageSize;
  source?: unknown;
};

export type BackendYoloBox = {
  detectionId?: string;
  classId?: number;
  label?: string;
  confidence: number;
  xPx: number;
  yPx: number;
  widthPx: number;
  heightPx: number;
};

export type YoloInferenceBackendResult =
  | {
      status: "ok";
      boxes: BackendYoloBox[];
      warnings?: string[];
    }
  | {
      status: "blocked";
      message: string;
      warnings?: string[];
    };

export interface YoloInferenceBackend {
  readonly name: string;
  infer(frame: YoloInferenceFrame): Promise<YoloInferenceBackendResult>;
  stop?(): void;
}

export type DetectionBox = {
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

const TENNIS_BALL_CLASS_ID = 0;
const TENNIS_BALL_LABEL = "tennis_ball";

export function createStereoYoloInferenceIdleStatus(): StereoYoloInferenceRuntimeStatus {
  return {
    left: createYoloInferenceIdleStatus("left"),
    right: createYoloInferenceIdleStatus("right"),
  };
}

export function createYoloInferenceIdleStatus(side: CameraSide): YoloInferenceRuntimeStatus {
  return {
    side,
    state: "idle",
    code: "not-started",
    label: `${capitalize(side)} YOLO idle`,
    detail:
      "YOLO adapter has not been started. Fixture overlays remain fixture-only until a backend produces runtime detections.",
    detectionCount: 0,
    detections: [],
    warnings: [],
  };
}

export function createYoloInferenceRunningStatus(
  side: CameraSide,
  frameId: string,
  timestampUnixMs: number,
): YoloInferenceRuntimeStatus {
  return {
    side,
    state: "running",
    code: "running",
    label: `${capitalize(side)} YOLO running`,
    detail: "Running the injected YOLO inference backend for the current camera frame.",
    frameId,
    timestampUnixMs,
    detectionCount: 0,
    detections: [],
    warnings: [],
  };
}

export function createBlockedYoloInferenceBackend(message: string): YoloInferenceBackend {
  return {
    name: "blocked-adapter",
    async infer(): Promise<YoloInferenceBackendResult> {
      return { status: "blocked", message };
    },
  };
}

export async function runYoloInferenceForFrame(
  backend: YoloInferenceBackend,
  frame: YoloInferenceFrame,
): Promise<YoloInferenceRuntimeStatus> {
  try {
    const result = await backend.infer(frame);
    if (result.status === "blocked") {
      return {
        side: frame.side,
        state: "blocked",
        code: "backend-blocked",
        label: `${capitalize(frame.side)} YOLO blocked`,
        detail: result.message,
        frameId: frame.frameId,
        timestampUnixMs: frame.timestampUnixMs,
        imageSize: frame.imageSize,
        detectionCount: 0,
        detections: [],
        warnings: result.warnings ?? [],
      };
    }

    const converted = convertBackendYoloBoxesToDetections({
      boxes: result.boxes,
      cameraId: frame.cameraId,
      frameId: frame.frameId,
      timestampUnixMs: frame.timestampUnixMs,
      imageSize: frame.imageSize,
    });
    const warnings = [...(result.warnings ?? []), ...converted.warnings];

    const hasValidDetections = converted.detections.length > 0;
    const hasOnlyRejectedBoxes = result.boxes.length > 0 && !hasValidDetections;
    const state = hasOnlyRejectedBoxes ? "blocked" : "ready";
    const code = hasOnlyRejectedBoxes ? "invalid-output" : "updated";
    const label = hasOnlyRejectedBoxes
      ? `${capitalize(frame.side)} YOLO output blocked`
      : `${capitalize(frame.side)} YOLO updated`;
    const detail = hasValidDetections
      ? `${backend.name} produced ${converted.detections.length} runtime detection(s).`
      : hasOnlyRejectedBoxes
        ? "Backend output did not contain any valid tennis-ball boxes."
        : `${backend.name} produced no tennis-ball detections for this frame.`;

    return {
      side: frame.side,
      state,
      code,
      label,
      detail,
      frameId: frame.frameId,
      timestampUnixMs: frame.timestampUnixMs,
      imageSize: frame.imageSize,
      detectionCount: converted.detections.length,
      detections: converted.detections,
      warnings,
    };
  } catch (error) {
    return {
      side: frame.side,
      state: "blocked",
      code: "backend-blocked",
      label: `${capitalize(frame.side)} YOLO blocked`,
      detail: `YOLO backend failed: ${formatUnknownError(error)}`,
      frameId: frame.frameId,
      timestampUnixMs: frame.timestampUnixMs,
      imageSize: frame.imageSize,
      detectionCount: 0,
      detections: [],
      warnings: [],
    };
  }
}

export function convertBackendYoloBoxesToDetections(options: {
  boxes: BackendYoloBox[];
  cameraId: string;
  frameId: string;
  timestampUnixMs: number;
  imageSize: ImageSize;
}): { detections: YoloDetection2D[]; warnings: string[] } {
  const detections: YoloDetection2D[] = [];
  const warnings: string[] = [];

  options.boxes.forEach((box, index) => {
    if (!isSupportedTennisBallBox(box)) {
      warnings.push(`box ${index} rejected because it is not class 0 tennis_ball`);
      return;
    }

    const normalized = normalizeBackendBox(box, options.imageSize);
    if (normalized === null) {
      warnings.push(`box ${index} rejected because its geometry or confidence is invalid`);
      return;
    }

    detections.push({
      detectionId:
        box.detectionId ??
        `${options.cameraId}-${options.frameId}-tennis-ball-${index}`,
      cameraId: options.cameraId,
      frameId: options.frameId,
      timestampUnixMs: options.timestampUnixMs,
      classId: TENNIS_BALL_CLASS_ID,
      label: TENNIS_BALL_LABEL,
      confidence: normalized.confidence,
      bboxPx: {
        xPx: normalized.xPx,
        yPx: normalized.yPx,
        widthPx: normalized.widthPx,
        heightPx: normalized.heightPx,
      },
      centerPx: {
        x: normalized.xPx + normalized.widthPx / 2,
        y: normalized.yPx + normalized.heightPx / 2,
      },
    });
  });

  return { detections, warnings };
}

export function detectionToOverlayBox(
  detection: YoloDetection2D,
  imageSize: ImageSize,
): DetectionBox {
  return {
    label: detection.label,
    confidence: detection.confidence,
    x: (detection.bboxPx.xPx / imageSize.widthPx) * 100,
    y: (detection.bboxPx.yPx / imageSize.heightPx) * 100,
    width: (detection.bboxPx.widthPx / imageSize.widthPx) * 100,
    height: (detection.bboxPx.heightPx / imageSize.heightPx) * 100,
  };
}

function normalizeBackendBox(
  box: BackendYoloBox,
  imageSize: ImageSize,
):
  | {
      confidence: number;
      xPx: number;
      yPx: number;
      widthPx: number;
      heightPx: number;
    }
  | null {
  const values = [box.confidence, box.xPx, box.yPx, box.widthPx, box.heightPx];
  if (!values.every(Number.isFinite) || box.confidence < 0 || box.confidence > 1) {
    return null;
  }
  if (box.widthPx <= 0 || box.heightPx <= 0) {
    return null;
  }
  if (imageSize.widthPx <= 0 || imageSize.heightPx <= 0) {
    return null;
  }

  const x1 = clamp(box.xPx, 0, imageSize.widthPx);
  const y1 = clamp(box.yPx, 0, imageSize.heightPx);
  const x2 = clamp(box.xPx + box.widthPx, 0, imageSize.widthPx);
  const y2 = clamp(box.yPx + box.heightPx, 0, imageSize.heightPx);
  const widthPx = x2 - x1;
  const heightPx = y2 - y1;

  if (widthPx <= 0 || heightPx <= 0) {
    return null;
  }

  return {
    confidence: box.confidence,
    xPx: x1,
    yPx: y1,
    widthPx,
    heightPx,
  };
}

function isSupportedTennisBallBox(box: BackendYoloBox): boolean {
  if (box.classId !== undefined && box.classId !== TENNIS_BALL_CLASS_ID) {
    return false;
  }
  if (box.label !== undefined && box.label !== TENNIS_BALL_LABEL) {
    return false;
  }
  return true;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
