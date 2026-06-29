export type JsonObject = Record<string, unknown>;

export type ArtifactKind =
  | "targetSheet"
  | "targetPrintCheck"
  | "captureManifest"
  | "captureInspection"
  | "charucoObservations"
  | "monoPackage"
  | "stereoPackage"
  | "packageVerification"
  | "cameraIntrinsics"
  | "unknown";

export type ImportedArtifact = {
  id: string;
  name: string;
  kind: ArtifactKind;
  payload: JsonObject;
};

export type WorkflowStage = {
  id: string;
  label: string;
  state: "ready" | "blocked" | "missing";
  detail: string;
  metric?: string;
};

export type CaptureFramePreview = {
  key: string;
  path: string;
  side: string;
  cameraId: string;
  index: string;
  status: string;
  luma: string;
  contrast: string;
  size: string;
  issues: string;
  imageUrl?: string;
};

export type ArtifactFileLink = {
  label: string;
  path: string;
  url?: string;
};

export type CaptureCommandOptions = {
  topology: "mono" | "stereo";
  cameraId: string;
  leftCameraId: string;
  rightCameraId: string;
  device: string;
  leftDevice: string;
  rightDevice: string;
  output: string;
  frameCount: number;
  pairCount: number;
  width: number;
  height: number;
  intervalMs: number;
  prepareUvcControls: boolean;
};

export type TargetCommandOptions = {
  output: string;
  outputReport: string;
  dpi: number;
  marginMm: number;
};

export type TargetPrintCheckCommandOptions = {
  measuredSquareMm: number;
  toleranceMm: number;
  output: string;
  outputReport: string;
};

export type SolveCommandOptions = {
  topology: "mono" | "stereo";
  observations: string;
  output: string;
  cameraId: string;
  leftMono: string;
  rightMono: string;
  minViews: number;
  minPairs: number;
  maxRmsPx: number;
};

export function classifyArtifact(payload: JsonObject): ArtifactKind {
  const schema = stringField(payload, "schema_version");
  const packageType = stringField(payload, "package_type");
  if (schema === "calibration.target_sheet.v1") return "targetSheet";
  if (schema === "calibration.target_print_check.v1") return "targetPrintCheck";
  if (schema === "calibration.capture_session.v1") return "captureManifest";
  if (schema === "calibration.capture_inspection.v1") return "captureInspection";
  if (schema === "calibration.charuco_observations.v1") return "charucoObservations";
  if (schema === "calibration.package_verification.v1") return "packageVerification";
  if (schema === "calibration.camera_intrinsics.v1") return "cameraIntrinsics";
  if (schema === "calibration.mono.v1" || packageType === "mono_camera_calibration") return "monoPackage";
  if (schema === "calibration.stereo.v1" || packageType === "stereo_camera_calibration") return "stereoPackage";
  return "unknown";
}

export function summarizeWorkflow(artifacts: ImportedArtifact[]): WorkflowStage[] {
  const targetSheet = latest(artifacts, "targetSheet");
  const targetPrintCheck = latest(artifacts, "targetPrintCheck");
  const manifest = latest(artifacts, "captureManifest");
  const inspection = latest(artifacts, "captureInspection");
  const observations = latest(artifacts, "charucoObservations");
  const monoPackage = latest(artifacts, "monoPackage");
  const stereoPackage = latest(artifacts, "stereoPackage");

  return [
    {
      id: "target",
      label: "Target",
      state: booleanField(targetSheet?.payload, "accepted") ? "ready" : targetSheet ? "blocked" : "missing",
      detail: targetSheet ? targetSheetDetail(targetSheet.payload) : "No target sheet loaded.",
      metric: targetSheet ? targetSheetMetric(targetSheet.payload) : undefined,
    },
    {
      id: "target-print",
      label: "Print Check",
      state: booleanField(targetPrintCheck?.payload, "accepted")
        ? "ready"
        : targetPrintCheck
          ? "blocked"
          : "missing",
      detail: targetPrintCheck ? targetPrintCheckDetail(targetPrintCheck.payload) : "No printed target measurement loaded.",
      metric: targetPrintCheck ? targetPrintCheckMetric(targetPrintCheck.payload) : undefined,
    },
    {
      id: "capture",
      label: "Capture",
      state: manifest ? "ready" : "missing",
      detail: manifest ? captureDetail(manifest.payload) : "No capture manifest loaded.",
    },
    {
      id: "inspect",
      label: "Inspect",
      state: booleanField(inspection?.payload, "accepted") ? "ready" : inspection ? "blocked" : "missing",
      detail: inspection ? inspectionDetail(inspection.payload) : "No inspection report loaded.",
      metric: inspection ? countMetric(inspection.payload, "read_image_count", "image_count") : undefined,
    },
    {
      id: "detect",
      label: "Detect",
      state: booleanField(observations?.payload, "accepted") ? "ready" : observations ? "blocked" : "missing",
      detail: observations ? observationDetail(observations.payload) : "No ChArUco observations loaded.",
      metric: observations ? observationMetric(observations.payload) : undefined,
    },
    {
      id: "mono",
      label: "Mono Solve",
      state: booleanField(monoPackage?.payload, "accepted") ? "ready" : monoPackage ? "blocked" : "missing",
      detail: monoPackage ? monoPackageDetail(monoPackage.payload) : "No mono package loaded.",
      metric: qualityMetric(monoPackage?.payload, "rms_reprojection_px"),
    },
    {
      id: "stereo",
      label: "Stereo Solve",
      state: booleanField(stereoPackage?.payload, "accepted") ? "ready" : stereoPackage ? "blocked" : "missing",
      detail: stereoPackage ? stereoPackageDetail(stereoPackage.payload) : "No stereo package loaded.",
      metric: qualityMetric(stereoPackage?.payload, "stereo_rms_reprojection_px"),
    },
  ];
}

export function buildTargetCommand(options: TargetCommandOptions): string {
  return joinCommand([
    "uv run tennisbot-calibration target charuco",
    `--output ${quote(options.output)}`,
    `--output-report ${quote(options.outputReport)}`,
    `--dpi ${options.dpi}`,
    `--margin-mm ${options.marginMm}`,
  ]);
}

export function buildTargetPrintCheckCommand(options: TargetPrintCheckCommandOptions): string {
  return joinCommand([
    "uv run tennisbot-calibration target record-print-check",
    `--measured-square-mm ${options.measuredSquareMm}`,
    `--tolerance-mm ${options.toleranceMm}`,
    `--output ${quote(options.output)}`,
    `--output-report ${quote(options.outputReport)}`,
  ]);
}

export function buildCaptureCommand(options: CaptureCommandOptions): string {
  if (options.topology === "mono") {
    return joinCommand([
      "uv run tennisbot-calibration capture mono",
      `--camera-id ${quote(options.cameraId)}`,
      `--device ${quote(options.device)}`,
      `--output ${quote(options.output)}`,
      `--frame-count ${options.frameCount}`,
      `--interval-ms ${options.intervalMs}`,
      `--width ${options.width}`,
      `--height ${options.height}`,
      options.prepareUvcControls ? "--prepare-uvc-controls" : "",
    ]);
  }
  return joinCommand([
    "uv run tennisbot-calibration capture stereo",
    `--left-camera-id ${quote(options.leftCameraId)}`,
    `--right-camera-id ${quote(options.rightCameraId)}`,
    `--left-device ${quote(options.leftDevice)}`,
    `--right-device ${quote(options.rightDevice)}`,
    `--output ${quote(options.output)}`,
    `--pair-count ${options.pairCount}`,
    `--interval-ms ${options.intervalMs}`,
    `--width ${options.width}`,
    `--height ${options.height}`,
    options.prepareUvcControls ? "--prepare-uvc-controls" : "",
  ]);
}

export function buildInspectCommand(sessionPath: string, reportPath: string): string {
  return joinCommand([
    "uv run tennisbot-calibration capture inspect",
    `--session ${quote(sessionPath)}`,
    `--output-report ${quote(reportPath)}`,
  ]);
}

export function buildDetectCommand(sessionPath: string, observationsPath: string, reportPath: string): string {
  return joinCommand([
    "uv run tennisbot-calibration capture detect-charuco",
    `--session ${quote(sessionPath)}`,
    `--output ${quote(observationsPath)}`,
    `--output-report ${quote(reportPath)}`,
  ]);
}

export function buildSolveCommand(options: SolveCommandOptions): string {
  if (options.topology === "mono") {
    return joinCommand([
      "uv run tennisbot-calibration calibrate mono",
      `--observations ${quote(options.observations)}`,
      `--output ${quote(options.output)}`,
      `--camera-id ${quote(options.cameraId)}`,
      `--min-views ${options.minViews}`,
      `--max-rms-px ${options.maxRmsPx}`,
    ]);
  }
  return joinCommand([
    "uv run tennisbot-calibration calibrate stereo",
    `--observations ${quote(options.observations)}`,
    `--left-mono ${quote(options.leftMono)}`,
    `--right-mono ${quote(options.rightMono)}`,
    `--output ${quote(options.output)}`,
    `--min-pairs ${options.minPairs}`,
    `--max-rms-px ${options.maxRmsPx}`,
  ]);
}

export function buildVerifyCommand(path: string): string {
  return joinCommand(["uv run tennisbot-calibration package verify", `--path ${quote(path)}`]);
}

export function frameRows(payload: JsonObject | undefined): Array<Record<string, string>> {
  const frames = arrayField(payload, "frames");
  return frames.map((frame) => {
    const item = objectValue(frame);
    return {
      path: stringField(item, "path") ?? "-",
      side: stringField(item, "side") ?? "-",
      status: stringField(item, "status") ?? "-",
      luma: numberDisplay(item["mean_luma"]),
      contrast: numberDisplay(item["std_luma"]),
      issues: arrayField(item, "issues").join(", ") || "none",
    };
  });
}

export function captureFramePreviews(
  manifest: JsonObject | undefined,
  inspection: JsonObject | undefined,
): CaptureFramePreview[] {
  const sessionPath = sessionPathForPreview(manifest, inspection);
  const previews = new Map<string, CaptureFramePreview>();

  for (const entry of manifestFrameEntries(manifest)) {
    const path = stringField(entry, "path") ?? "-";
    previews.set(path, previewFromFrame(entry, sessionPath, "captured"));
  }

  for (const frame of arrayField(inspection, "frames")) {
    const entry = objectValue(frame);
    const path = stringField(entry, "path") ?? "-";
    previews.set(path, {
      ...(previews.get(path) ?? previewFromFrame(entry, sessionPath, "captured")),
      ...previewFromFrame(entry, sessionPath, stringField(entry, "status") ?? "read"),
    });
  }

  return [...previews.values()];
}

export function observationRows(payload: JsonObject | undefined): Array<Record<string, string>> {
  const views = arrayField(payload, "views");
  return views.map((view) => {
    const item = objectValue(view);
    return {
      path: stringField(item, "path") ?? "-",
      side: stringField(item, "side") ?? "-",
      accepted: String(booleanField(item, "accepted")),
      corners: numberDisplay(item["corner_count"]),
      markers: numberDisplay(item["marker_count"]),
      reason: stringField(item, "rejection_reason") ?? "none",
    };
  });
}

export function targetSheetFileLinks(payload: JsonObject | undefined): ArtifactFileLink[] {
  const files = objectField(payload, "files");
  return ["svg", "png", "metadata"]
    .map((label) => {
      const path = stringField(files, label);
      return path === undefined ? undefined : { label, path, url: artifactFileUrl(path) };
    })
    .filter((item): item is ArtifactFileLink => item !== undefined);
}

export function latest(artifacts: ImportedArtifact[], kind: ArtifactKind): ImportedArtifact | undefined {
  return [...artifacts].reverse().find((artifact) => artifact.kind === kind);
}

function manifestFrameEntries(manifest: JsonObject | undefined): JsonObject[] {
  if (manifest === undefined) return [];
  if (stringField(manifest, "topology") === "mono") {
    return arrayField(manifest, "files").map((file, index) => ({
      index: index + 1,
      camera_id: stringField(manifest, "camera_id") ?? "mono",
      side: "mono",
      path: typeof file === "string" ? file : "-",
    }));
  }

  if (stringField(manifest, "topology") === "stereo") {
    const cameraIds = arrayField(manifest, "camera_ids");
    const leftCameraId = typeof cameraIds[0] === "string" ? cameraIds[0] : "left";
    const rightCameraId = typeof cameraIds[1] === "string" ? cameraIds[1] : "right";
    return arrayField(manifest, "pairs").flatMap((pair, pairIndex) => {
      const item = objectValue(pair);
      const index = item["index"] ?? pairIndex + 1;
      return [
        {
          index,
          camera_id: leftCameraId,
          side: "left",
          path: stringField(item, "left") ?? "-",
        },
        {
          index,
          camera_id: rightCameraId,
          side: "right",
          path: stringField(item, "right") ?? "-",
        },
      ];
    });
  }

  return [];
}

function previewFromFrame(
  frame: JsonObject,
  sessionPath: string | undefined,
  fallbackStatus: string,
): CaptureFramePreview {
  const path = stringField(frame, "path") ?? "-";
  return {
    key: `${stringField(frame, "side") ?? "-"}:${path}`,
    path,
    side: stringField(frame, "side") ?? "-",
    cameraId: stringField(frame, "camera_id") ?? "-",
    index: numberDisplay(frame["index"]),
    status: stringField(frame, "status") ?? fallbackStatus,
    luma: numberDisplay(frame["mean_luma"]),
    contrast: numberDisplay(frame["std_luma"]),
    size: frameSize(frame),
    issues: arrayField(frame, "issues").join(", ") || "none",
    imageUrl: artifactImageUrl(sessionPath, path),
  };
}

function frameSize(frame: JsonObject): string {
  const width = frame["width"];
  const height = frame["height"];
  return typeof width === "number" && typeof height === "number" ? `${width}x${height}` : "-";
}

function sessionPathForPreview(
  manifest: JsonObject | undefined,
  inspection: JsonObject | undefined,
): string | undefined {
  return stringField(inspection, "session_path") ?? stringField(manifest, "session_path");
}

function artifactImageUrl(sessionPath: string | undefined, framePath: string): string | undefined {
  if (framePath === "-" || framePath.trim() === "") return undefined;
  const candidate =
    framePath.startsWith("/artifacts/") || framePath.startsWith("artifacts/")
      ? framePath
      : sessionPath === undefined
        ? undefined
        : `${sessionPath}/${framePath}`;
  if (candidate === undefined) return undefined;
  return artifactFileUrl(candidate, [".png", ".jpg", ".jpeg"]);
}

function artifactFileUrl(candidate: string, allowedExtensions = [".png", ".jpg", ".jpeg", ".svg", ".json"]): string | undefined {
  const segments = candidate.replaceAll("\\", "/").split("/");
  const artifactsIndex = segments.lastIndexOf("artifacts");
  if (artifactsIndex < 0) return undefined;
  const artifactSegments = segments.slice(artifactsIndex + 1);
  if (
    artifactSegments.length === 0 ||
    artifactSegments.some((segment) => segment === "" || segment === "." || segment === "..")
  ) {
    return undefined;
  }
  const last = artifactSegments.at(-1)?.toLowerCase() ?? "";
  if (!allowedExtensions.some((extension) => last.endsWith(extension))) {
    return undefined;
  }
  return `/artifacts/${artifactSegments.map((segment) => encodeURIComponent(segment)).join("/")}`;
}

function captureDetail(payload: JsonObject): string {
  const topology = stringField(payload, "topology") ?? "unknown";
  const sessionId = stringField(payload, "session_id") ?? "unknown";
  if (topology === "stereo") {
    return `${sessionId}: stereo ${numberDisplay(payload["pair_count"])} pair(s).`;
  }
  return `${sessionId}: mono ${numberDisplay(payload["frame_count"])} frame(s).`;
}

function targetSheetDetail(payload: JsonObject): string {
  const target = objectField(payload, "target");
  return `${stringField(target, "profile") ?? "unknown"}: ${numberDisplay(target?.["squares_x"])} x ${numberDisplay(target?.["squares_y"])}.`;
}

function targetSheetMetric(payload: JsonObject): string {
  const target = objectField(payload, "target");
  const squareSizeM = target?.["square_size_m"];
  return typeof squareSizeM === "number" ? `${Number((squareSizeM * 1000).toFixed(3))} mm` : "ready";
}

function targetPrintCheckDetail(payload: JsonObject): string {
  return booleanField(payload, "accepted")
    ? `Measured square ${numberDisplay(payload["measured_square_mm"])} mm.`
    : `Measured square ${numberDisplay(payload["measured_square_mm"])} mm is outside tolerance.`;
}

function targetPrintCheckMetric(payload: JsonObject): string {
  const delta = payload["delta_mm"];
  return typeof delta === "number" ? `${Number(delta.toFixed(3))} mm delta` : "checked";
}

function inspectionDetail(payload: JsonObject): string {
  const recommendation = stringField(payload, "recommendation");
  return recommendation ?? `${numberDisplay(payload["read_image_count"])} image(s) read.`;
}

function observationDetail(payload: JsonObject): string {
  const topology = stringField(payload, "topology") ?? "unknown";
  if (topology === "stereo") {
    return `${numberDisplay(payload["accepted_pair_count"])} / ${numberDisplay(payload["total_pair_count"])} pair(s) accepted.`;
  }
  return `${numberDisplay(payload["accepted_view_count"])} / ${numberDisplay(payload["total_view_count"])} view(s) accepted.`;
}

function observationMetric(payload: JsonObject): string {
  if (stringField(payload, "topology") === "stereo") {
    return countMetric(payload, "accepted_pair_count", "total_pair_count");
  }
  return countMetric(payload, "accepted_view_count", "total_view_count");
}

function monoPackageDetail(payload: JsonObject): string {
  const cameraId = stringField(payload, "camera_id") ?? "unknown";
  const quality = objectField(payload, "quality");
  return `${cameraId}: RMS ${numberDisplay(quality?.["rms_reprojection_px"])} px.`;
}

function stereoPackageDetail(payload: JsonObject): string {
  const cameraIds = arrayField(payload, "camera_ids").join(", ") || "unknown";
  const quality = objectField(payload, "quality");
  return `${cameraIds}: RMS ${numberDisplay(quality?.["stereo_rms_reprojection_px"])} px.`;
}

function countMetric(payload: JsonObject, acceptedKey: string, totalKey: string): string {
  return `${numberDisplay(payload[acceptedKey])} / ${numberDisplay(payload[totalKey])}`;
}

function qualityMetric(payload: JsonObject | undefined, key: string): string | undefined {
  const quality = objectField(payload, "quality");
  const value = quality?.[key];
  return typeof value === "number" ? `${value.toFixed(3)} px` : undefined;
}

function joinCommand(parts: string[]): string {
  return parts.filter(Boolean).join(" \\\n  ");
}

function quote(value: string): string {
  return value.includes(" ") ? JSON.stringify(value) : value;
}

function stringField(payload: JsonObject | undefined, key: string): string | undefined {
  const value = payload?.[key];
  return typeof value === "string" ? value : undefined;
}

function booleanField(payload: JsonObject | undefined, key: string): boolean {
  return payload?.[key] === true;
}

function objectField(payload: JsonObject | undefined, key: string): JsonObject | undefined {
  return objectValue(payload?.[key]);
}

function objectValue(value: unknown): JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : {};
}

function arrayField(payload: JsonObject | undefined, key: string): unknown[] {
  const value = payload?.[key];
  return Array.isArray(value) ? value : [];
}

function numberDisplay(value: unknown): string {
  return typeof value === "number" && Number.isFinite(value) ? String(Number(value.toFixed(3))) : "-";
}
