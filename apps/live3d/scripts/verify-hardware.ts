import { Buffer } from "node:buffer";
import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, extname, join, resolve } from "node:path";

import type { Live3dRuntimeSnapshot } from "../src/runtime-snapshot";

type Options = {
  appUrl: string;
  timeoutMs: number;
  pollMs: number;
  chromeDebugPort: number;
  chromeBin?: string;
  keepChrome: boolean;
  outputPath: string;
  captureDir: string;
  prepareUvcControls: boolean;
  uvcDevicePaths: string[];
};

type StepStatus = "passed" | "failed" | "skipped";
export type VerificationGateStatus = "passed" | "failed" | "blocked" | "unknown";

type VerificationStep = {
  name: string;
  status: StepStatus;
  detail: string;
};

type Observation = {
  snapshotsSeen: number;
  maxLeftDetections: number;
  maxRightDetections: number;
  maxTrailLength: number;
  maxPredictionSamples: number;
  runtimeCodes: string[];
  lastSnapshot: Live3dRuntimeSnapshot | null;
};

type CaptureArtifact = {
  label: "left" | "right";
  path?: string;
  status: "saved" | "failed";
  detail: string;
  meanLuma?: number;
  maxLuma?: number;
  nonBlackPixelPercent?: number;
};

export type VerificationResult = {
  status: "passed" | "failed" | "error";
  startedAt: Date;
  finishedAt: Date;
  appUrl: string;
  steps: VerificationStep[];
  observation: Observation;
  captures: CaptureArtifact[];
  error?: string;
};

export type VerificationGate = {
  id: string;
  label: string;
  status: VerificationGateStatus;
  detail: string;
  evidence: string;
  nextAction?: string;
};

type SpawnedProcess = ReturnType<typeof Bun.spawn>;

type CdpResponse = {
  id?: number;
  result?: unknown;
  error?: { message?: string; data?: string };
};

type RuntimeEvaluateResult = {
  result?: {
    type?: string;
    value?: unknown;
    description?: string;
  };
  exceptionDetails?: {
    text?: string;
  };
};

const appDir = resolve(import.meta.dirname, "..");
const repoRoot = resolve(appDir, "..", "..");
const defaultTimeoutMs = 30_000;
const defaultPollMs = 500;
const defaultChromeDebugPort = 9233;

if (import.meta.main) {
  await main(Bun.argv.slice(2));
}

export async function main(args: string[]): Promise<void> {
  const options = parseArgs(args);
  const startedAt = new Date();

  try {
    const result = await runVerification(startedAt, options);
    writeReport(result, options.outputPath);
    console.log(`Live3D hardware verification report: ${options.outputPath}`);
    process.exitCode = result.status === "passed" ? 0 : 1;
  } catch (error) {
    const result: VerificationResult = {
      status: "error",
      startedAt,
      finishedAt: new Date(),
      appUrl: options.appUrl,
      steps: [],
      observation: createEmptyObservation(),
      captures: [],
      error: formatUnknownError(error),
    };
    writeReport(result, options.outputPath);
    console.error(result.error);
    console.error(`Live3D hardware verification report: ${options.outputPath}`);
    process.exitCode = 1;
  }
}

async function runVerification(startedAt: Date, opts: Options): Promise<VerificationResult> {
  const steps: VerificationStep[] = [];
  const observation = createEmptyObservation();
  let serverProcess: SpawnedProcess | undefined;
  let chromeProcess: SpawnedProcess | undefined;
  let chromeProfileDir: string | undefined;
  let cdp: CdpClient | undefined;

  try {
    await prepareUvcCameraControls(opts, steps);
    serverProcess = await ensureLive3dServer(opts, steps);
    const chrome = await launchChrome(opts, steps);
    chromeProcess = chrome.process;
    chromeProfileDir = chrome.profileDir;

    const tab = await openChromeTab(opts, steps);
    cdp = await CdpClient.connect(tab.webSocketDebuggerUrl);
    await cdp.send("Runtime.enable");
    await cdp.send("Page.enable");
    await cdp.send("Page.navigate", { url: opts.appUrl });

    const initialSnapshot = await waitForSnapshot(cdp, opts.timeoutMs, opts.pollMs);
    recordSnapshot(observation, initialSnapshot);
    steps.push({
      name: "page snapshot",
      status: "passed",
      detail: "window.__tennisbotLive3dSnapshot is available.",
    });

    if (initialSnapshot.yoloArtifact.status !== "loaded") {
      return await finalizeResult(
        failed(startedAt, opts, steps, observation, "YOLO artifact is blocked."),
        cdp,
        opts,
      );
    }
    if (initialSnapshot.calibrationArtifact.status !== "loaded") {
      return await finalizeResult(
        failed(startedAt, opts, steps, observation, "Stereo calibration artifact is blocked."),
        cdp,
        opts,
      );
    }

    await evaluate(cdp, `document.querySelector("#camera-start-button")?.click(); true`);
    const cameraSnapshot = await pollSnapshots(cdp, opts, observation, (snapshot) =>
      snapshot.camera.state === "ready" || snapshot.camera.state === "blocked",
    );
    if (cameraSnapshot.camera.state !== "ready") {
      steps.push({
        name: "camera startup",
        status: "failed",
        detail: cameraSnapshot.camera.left.detail + " " + cameraSnapshot.camera.right.detail,
      });
      return await finalizeResult(
        failed(startedAt, opts, steps, observation, "Two real USB camera streams did not reach ready."),
        cdp,
        opts,
      );
    }
    steps.push({
      name: "camera startup",
      status: "passed",
      detail: `${cameraSnapshot.camera.deviceCount} video input(s); left=${cameraSnapshot.camera.left.deviceLabel ?? cameraSnapshot.camera.left.deviceId ?? "unknown"}; right=${cameraSnapshot.camera.right.deviceLabel ?? cameraSnapshot.camera.right.deviceId ?? "unknown"}.`,
    });

    await evaluate(cdp, `document.querySelector("#yolo-start-button")?.click(); true`);
    const runtimeSnapshot = await pollSnapshots(cdp, opts, observation, (snapshot) =>
      snapshot.runtime3d.code === "prediction-ready",
    );
    if (runtimeSnapshot.runtime3d.code !== "prediction-ready") {
      steps.push({
        name: "runtime 3D prediction",
        status: "failed",
        detail: failureDetail(observation),
      });
      return await finalizeResult(
        failed(startedAt, opts, steps, observation, "Runtime 3D prediction did not reach ready."),
        cdp,
        opts,
      );
    }

    steps.push({
      name: "runtime 3D prediction",
      status: "passed",
      detail: `left max detections=${observation.maxLeftDetections}, right max detections=${observation.maxRightDetections}, trail=${observation.maxTrailLength}, samples=${observation.maxPredictionSamples}.`,
    });

    return await finalizeResult(
      {
        status: "passed",
        startedAt,
        finishedAt: new Date(),
        appUrl: opts.appUrl,
        steps,
        observation,
        captures: [],
      },
      cdp,
      opts,
    );
  } finally {
    if (cdp !== undefined) {
      cdp.close();
    }
    if (chromeProcess !== undefined && !opts.keepChrome) {
      chromeProcess.kill();
    }
    if (chromeProfileDir !== undefined && !opts.keepChrome) {
      rmSync(chromeProfileDir, { recursive: true, force: true });
    }
    if (serverProcess !== undefined) {
      serverProcess.kill();
    }
  }
}

async function prepareUvcCameraControls(
  opts: Options,
  steps: VerificationStep[],
): Promise<void> {
  if (!opts.prepareUvcControls) {
    return;
  }

  for (const devicePath of opts.uvcDevicePaths) {
    await runCommand(
      [
        "v4l2-ctl",
        "-d",
        devicePath,
        "--set-ctrl=brightness=64,gain=255,auto_exposure=1,exposure_time_absolute=2047",
      ],
      repoRoot,
    );
  }

  steps.push({
    name: "uvc controls",
    status: "passed",
    detail: `Applied brightness=64, gain=255, manual exposure=2047 to ${opts.uvcDevicePaths.join(", ")}.`,
  });
}

async function finalizeResult(
  result: VerificationResult,
  cdp: CdpClient | undefined,
  opts: Options,
): Promise<VerificationResult> {
  if (cdp === undefined) {
    return result;
  }

  try {
    result.captures = await captureVideoFrames(cdp, opts.captureDir);
    const savedCount = result.captures.filter((capture) => capture.status === "saved").length;
    const darkCaptures = result.captures.filter(
      (capture) => capture.status === "saved" && (capture.maxLuma ?? 0) <= 8,
    );
    result.steps.push({
      name: "frame capture",
      status: savedCount > 0 ? "passed" : "failed",
      detail:
        savedCount > 0
          ? `Saved ${savedCount} video frame capture(s) under ${opts.captureDir}.`
          : "No video frames could be captured from the page.",
    });
    if (darkCaptures.length > 0) {
      result.steps.push({
        name: "frame quality",
        status: "failed",
        detail: `${darkCaptures.map((capture) => capture.label).join(", ")} capture(s) are near-black; check camera exposure, lens cover, or browser capture backend before judging YOLO.`,
      });
    } else if (savedCount > 0) {
      result.steps.push({
        name: "frame quality",
        status: "passed",
        detail: "Captured frames are not near-black.",
      });
    }
  } catch (error) {
    result.captures = [
      {
        label: "left",
        status: "failed",
        detail: `Frame capture failed: ${formatUnknownError(error)}`,
      },
      {
        label: "right",
        status: "failed",
        detail: `Frame capture failed: ${formatUnknownError(error)}`,
      },
    ];
    result.steps.push({
      name: "frame capture",
      status: "failed",
      detail: formatUnknownError(error),
    });
  }

  result.finishedAt = new Date();
  return result;
}

async function ensureLive3dServer(
  opts: Options,
  steps: VerificationStep[],
): Promise<SpawnedProcess | undefined> {
  if (await isHttpOk(opts.appUrl)) {
    steps.push({
      name: "app server",
      status: "passed",
      detail: `${opts.appUrl} is already serving Live3D.`,
    });
    return undefined;
  }

  await runCommand(["bun", "run", "build"], appDir);
  const port = new URL(opts.appUrl).port || "80";
  const server = Bun.spawn(["bun", "./scripts/serve.js"], {
    cwd: appDir,
    env: { ...process.env, PORT: port },
    stdout: "pipe",
    stderr: "pipe",
    stdin: "ignore",
  });

  await waitUntil(async () => isHttpOk(opts.appUrl), 10_000, 250);
  steps.push({
    name: "app server",
    status: "passed",
    detail: `Started Live3D static server at ${opts.appUrl}.`,
  });
  return server;
}

async function launchChrome(
  opts: Options,
  steps: VerificationStep[],
): Promise<{ process: SpawnedProcess; profileDir: string }> {
  const chromeBin = opts.chromeBin ?? findChromeBinary();
  if (chromeBin === undefined) {
    throw new Error("Chrome/Chromium binary was not found. Set CHROME_BIN or pass --chrome-bin.");
  }

  const profileDir = mkdtempSync(join(tmpdir(), "tennisbot-live3d-chrome-"));
  const process = Bun.spawn(
    [
      chromeBin,
      `--remote-debugging-port=${opts.chromeDebugPort}`,
      `--user-data-dir=${profileDir}`,
      "--headless=new",
      "--use-fake-ui-for-media-stream",
      "--autoplay-policy=no-user-gesture-required",
      "--no-first-run",
      "--no-default-browser-check",
      "--no-sandbox",
      "about:blank",
    ],
    {
      stdout: "pipe",
      stderr: "pipe",
      stdin: "ignore",
    },
  );

  await waitUntil(async () => isHttpOk(chromeDebugUrl(opts, "/json/version")), 10_000, 250);
  steps.push({
    name: "chrome",
    status: "passed",
    detail: `${chromeBin} is listening on CDP port ${opts.chromeDebugPort}.`,
  });
  return { process, profileDir };
}

async function openChromeTab(
  opts: Options,
  steps: VerificationStep[],
): Promise<{ webSocketDebuggerUrl: string }> {
  const url = chromeDebugUrl(opts, `/json/new?${encodeURIComponent(opts.appUrl)}`);
  let response = await fetch(url, { method: "PUT" });
  if (!response.ok) {
    response = await fetch(url);
  }
  if (!response.ok) {
    throw new Error(`/json/new returned HTTP ${response.status}`);
  }
  const payload = await response.json();
  if (
    typeof payload !== "object" ||
    payload === null ||
    typeof (payload as { webSocketDebuggerUrl?: unknown }).webSocketDebuggerUrl !== "string"
  ) {
    throw new Error("Chrome /json/new did not return webSocketDebuggerUrl.");
  }

  steps.push({
    name: "chrome tab",
    status: "passed",
    detail: `Opened ${opts.appUrl}.`,
  });
  return payload as { webSocketDebuggerUrl: string };
}

async function waitForSnapshot(
  cdp: CdpClient,
  timeoutMs: number,
  pollMs: number,
): Promise<Live3dRuntimeSnapshot> {
  return waitUntil(async () => {
    const snapshot = await readSnapshot(cdp);
    return snapshot ?? undefined;
  }, timeoutMs, pollMs);
}

async function pollSnapshots(
  cdp: CdpClient,
  opts: Options,
  observation: Observation,
  done: (snapshot: Live3dRuntimeSnapshot) => boolean,
): Promise<Live3dRuntimeSnapshot> {
  let lastSnapshot: Live3dRuntimeSnapshot | null = null;
  const started = Date.now();
  while (Date.now() - started <= opts.timeoutMs) {
    const snapshot = await readSnapshot(cdp);
    if (snapshot !== null) {
      lastSnapshot = snapshot;
      recordSnapshot(observation, snapshot);
      if (done(snapshot)) {
        return snapshot;
      }
    }
    await sleep(opts.pollMs);
  }

  if (lastSnapshot === null) {
    throw new Error("Live3D runtime snapshot was never available.");
  }
  return lastSnapshot;
}

async function readSnapshot(cdp: CdpClient): Promise<Live3dRuntimeSnapshot | null> {
  const value = await evaluate(cdp, "window.__tennisbotLive3dSnapshot ?? null");
  if (value === null || typeof value !== "object") {
    return null;
  }
  return value as Live3dRuntimeSnapshot;
}

async function captureVideoFrames(cdp: CdpClient, captureDir: string): Promise<CaptureArtifact[]> {
  const captures = await evaluate(cdp, `
    (async () => {
      const drawImageSource = (label, source, width, height, method) => {
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext("2d");
        if (context === null) {
          return { label, ok: false, message: "2D canvas context is unavailable." };
        }
        context.drawImage(source, 0, 0, canvas.width, canvas.height);
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let lumaSum = 0;
        let maxLuma = 0;
        let nonBlackPixels = 0;
        for (let index = 0; index < pixels.length; index += 4) {
          const luma =
            0.2126 * pixels[index] +
            0.7152 * pixels[index + 1] +
            0.0722 * pixels[index + 2];
          lumaSum += luma;
          maxLuma = Math.max(maxLuma, luma);
          if (luma > 8) {
            nonBlackPixels += 1;
          }
        }
        const pixelCount = canvas.width * canvas.height;
        return {
          label,
          ok: true,
          width: canvas.width,
          height: canvas.height,
          method,
          meanLuma: lumaSum / pixelCount,
          maxLuma,
          nonBlackPixelPercent: (nonBlackPixels / pixelCount) * 100,
          dataUrl: canvas.toDataURL("image/png"),
        };
      };
      const waitForVideoFrame = (video) =>
        new Promise((resolve) => {
          if (typeof video.requestVideoFrameCallback === "function") {
            video.requestVideoFrameCallback(() => resolve());
          } else {
            setTimeout(resolve, 250);
          }
        });
      const capture = async (label, selector) => {
        const video = document.querySelector(selector);
        if (!(video instanceof HTMLVideoElement)) {
          return { label, ok: false, message: selector + " is not a video element." };
        }
        const stream = video.srcObject instanceof MediaStream ? video.srcObject : null;
        const track = stream?.getVideoTracks()[0];
        if (track !== undefined && typeof ImageCapture !== "undefined") {
          try {
            const bitmap = await new ImageCapture(track).grabFrame();
            return drawImageSource(label, bitmap, bitmap.width, bitmap.height, "image-capture");
          } catch {
            // Fall back to drawing the video element below.
          }
        }
        await waitForVideoFrame(video);
        if (video.videoWidth <= 0 || video.videoHeight <= 0) {
          return { label, ok: false, message: selector + " has no decoded video frame." };
        }
        return drawImageSource(label, video, video.videoWidth, video.videoHeight, "video-canvas");
      };
      return await Promise.all([
        capture("left", "#left-camera-video"),
        capture("right", "#right-camera-video"),
      ]);
    })()
  `);

  if (!Array.isArray(captures)) {
    throw new Error("Frame capture did not return an array.");
  }

  mkdirSync(captureDir, { recursive: true });
  return captures.map((capture, index) => saveCaptureArtifact(capture, captureDir, index));
}

async function evaluate(cdp: CdpClient, expression: string): Promise<unknown> {
  const result = (await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })) as RuntimeEvaluateResult;

  if (result.exceptionDetails !== undefined) {
    throw new Error(result.exceptionDetails.text ?? "Runtime.evaluate failed.");
  }

  return result.result?.value;
}

class CdpClient {
  private nextId = 1;
  private readonly pending = new Map<
    number,
    {
      resolve: (value: unknown) => void;
      reject: (error: Error) => void;
    }
  >();

  private constructor(private readonly socket: WebSocket) {
    socket.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data)) as CdpResponse;
      if (message.id === undefined) {
        return;
      }
      const pending = this.pending.get(message.id);
      if (pending === undefined) {
        return;
      }
      this.pending.delete(message.id);
      if (message.error !== undefined) {
        pending.reject(new Error(message.error.message ?? "CDP command failed."));
      } else {
        pending.resolve(message.result);
      }
    });
  }

  static connect(webSocketDebuggerUrl: string): Promise<CdpClient> {
    return new Promise((resolveConnect, rejectConnect) => {
      const socket = new WebSocket(webSocketDebuggerUrl);
      socket.addEventListener("open", () => resolveConnect(new CdpClient(socket)));
      socket.addEventListener("error", () => rejectConnect(new Error("CDP WebSocket connection failed.")));
    });
  }

  send(method: string, params?: Record<string, unknown>): Promise<unknown> {
    const id = this.nextId;
    this.nextId += 1;
    const payload = JSON.stringify({ id, method, params });
    return new Promise((resolveSend, rejectSend) => {
      this.pending.set(id, { resolve: resolveSend, reject: rejectSend });
      this.socket.send(payload);
    });
  }

  close(): void {
    this.socket.close();
  }
}

function recordSnapshot(observation: Observation, snapshot: Live3dRuntimeSnapshot): void {
  observation.snapshotsSeen += 1;
  observation.maxLeftDetections = Math.max(
    observation.maxLeftDetections,
    snapshot.detections.left.detectionCount,
  );
  observation.maxRightDetections = Math.max(
    observation.maxRightDetections,
    snapshot.detections.right.detectionCount,
  );
  observation.maxTrailLength = Math.max(observation.maxTrailLength, snapshot.runtime3d.trailLength);
  observation.maxPredictionSamples = Math.max(
    observation.maxPredictionSamples,
    snapshot.runtime3d.predictionSampleCount,
  );
  if (!observation.runtimeCodes.includes(snapshot.runtime3d.code)) {
    observation.runtimeCodes.push(snapshot.runtime3d.code);
  }
  observation.lastSnapshot = snapshot;
}

function failed(
  startedAt: Date,
  opts: Options,
  steps: VerificationStep[],
  observation: Observation,
  error: string,
): VerificationResult {
  return {
    status: "failed",
    startedAt,
    finishedAt: new Date(),
    appUrl: opts.appUrl,
    steps,
    observation,
    captures: [],
    error,
  };
}

function saveCaptureArtifact(capture: unknown, captureDir: string, index: number): CaptureArtifact {
  if (!isRawCapture(capture)) {
    return {
      label: index === 0 ? "left" : "right",
      status: "failed",
      detail: "Frame capture returned an invalid payload.",
    };
  }

  if (!capture.ok) {
    return {
      label: capture.label,
      status: "failed",
      detail: capture.message,
    };
  }

  const match = /^data:image\/png;base64,(.+)$/u.exec(capture.dataUrl);
  if (match === null) {
    return {
      label: capture.label,
      status: "failed",
      detail: "Frame capture did not return a PNG data URL.",
    };
  }

  const path = join(captureDir, `${capture.label}.png`);
  writeFileSync(path, Buffer.from(match[1], "base64"));
  return {
    label: capture.label,
    path,
    status: "saved",
    detail: `${capture.width}x${capture.height} PNG frame via ${capture.method ?? "unknown"}; mean luma ${capture.meanLuma.toFixed(2)}, max luma ${capture.maxLuma.toFixed(2)}, non-black ${capture.nonBlackPixelPercent.toFixed(2)}%.`,
    meanLuma: capture.meanLuma,
    maxLuma: capture.maxLuma,
    nonBlackPixelPercent: capture.nonBlackPixelPercent,
  };
}

function isRawCapture(
  value: unknown,
): value is
  | {
      label: "left" | "right";
      ok: true;
      width: number;
      height: number;
      method?: string;
      meanLuma: number;
      maxLuma: number;
      nonBlackPixelPercent: number;
      dataUrl: string;
    }
  | {
      label: "left" | "right";
      ok: false;
      message: string;
    } {
  if (typeof value !== "object" || value === null) {
    return false;
  }
  const raw = value as Record<string, unknown>;
  if (raw.label !== "left" && raw.label !== "right") {
    return false;
  }
  if (raw.ok === true) {
    return (
      typeof raw.width === "number" &&
      typeof raw.height === "number" &&
      typeof raw.meanLuma === "number" &&
      typeof raw.maxLuma === "number" &&
      typeof raw.nonBlackPixelPercent === "number" &&
      typeof raw.dataUrl === "string"
    );
  }
  return raw.ok === false && typeof raw.message === "string";
}

function failureDetail(observation: Observation): string {
  if (observation.maxLeftDetections === 0) {
    return "Left YOLO never produced a tennis-ball detection.";
  }
  if (observation.maxRightDetections === 0) {
    return "Right YOLO never produced a tennis-ball detection.";
  }
  if (observation.maxTrailLength < 1) {
    return "Both sides detected a ball, but no stereo pair triangulated.";
  }
  if (observation.maxTrailLength < 2) {
    return "Stereo triangulation produced only one 3D point; prediction needs two time-separated points.";
  }
  return "Runtime 3D did not publish prediction-ready before timeout.";
}

function createEmptyObservation(): Observation {
  return {
    snapshotsSeen: 0,
    maxLeftDetections: 0,
    maxRightDetections: 0,
    maxTrailLength: 0,
    maxPredictionSamples: 0,
    runtimeCodes: [],
    lastSnapshot: null,
  };
}

function writeReport(result: VerificationResult, outputPath: string): void {
  mkdirSync(dirname(outputPath), { recursive: true });
  writeFileSync(outputPath, renderReport(result), "utf-8");
}

export function createAcceptanceChecklist(result: VerificationResult): VerificationGate[] {
  const yoloGate = yoloArtifactGate(result);
  const calibrationGate = calibrationArtifactGate(result);
  const cameraGate = cameraGateFromSnapshot(result);
  const frameGate = frameQualityGate(result);
  const leftDetectionGate = detectionGate(
    "left-yolo-detection",
    "Left YOLO detection",
    result.observation.maxLeftDetections,
    yoloGate,
    cameraGate,
    frameGate,
  );
  const rightDetectionGate = detectionGate(
    "right-yolo-detection",
    "Right YOLO detection",
    result.observation.maxRightDetections,
    yoloGate,
    cameraGate,
    frameGate,
  );

  return [
    stepGate("app-server", "Live3D app server", result, "app server"),
    stepGate("page-snapshot", "Runtime snapshot export", result, "page snapshot"),
    yoloGate,
    calibrationGate,
    cameraGate,
    frameGate,
    leftDetectionGate,
    rightDetectionGate,
    triangulationGate(result, calibrationGate, leftDetectionGate, rightDetectionGate),
    predictionGate(result),
  ];
}

export function renderReport(result: VerificationResult): string {
  const last = result.observation.lastSnapshot;
  const checklist = renderAcceptanceChecklist(createAcceptanceChecklist(result));
  const readinessGates = renderRuntimeReadinessGates(last?.readinessGates ?? []);
  const steps =
    result.steps.length === 0
      ? "- No steps completed.\n"
      : result.steps
          .map((step) => `- ${step.status}: ${step.name} - ${step.detail}`)
          .join("\n") + "\n";
  const captures =
    result.captures.length === 0
      ? "- No frame captures were written.\n"
      : result.captures
          .map((capture) =>
            capture.path === undefined
              ? `- ${capture.status}: ${capture.label} - ${capture.detail}`
              : `- ${capture.status}: ${capture.label} - ${capture.detail} (${capture.path})`,
          )
          .join("\n") + "\n";

  return `# Live3D Hardware Loop Verification

- Started: ${result.startedAt.toISOString()}
- Finished: ${result.finishedAt.toISOString()}
- App URL: ${result.appUrl}
- Result: ${result.status}
- Error: ${result.error ?? "none"}

## Acceptance Checklist

${checklist}
## Runtime Readiness Gates

${readinessGates}
## Steps

${steps}
## Observations

- Snapshots seen: ${result.observation.snapshotsSeen}
- Max left detections: ${result.observation.maxLeftDetections}
- Max right detections: ${result.observation.maxRightDetections}
- Max trail length: ${result.observation.maxTrailLength}
- Max prediction samples: ${result.observation.maxPredictionSamples}
- Runtime 3D codes: ${result.observation.runtimeCodes.join(", ") || "none"}

## Frame Captures

${captures}

## Last Snapshot

\`\`\`json
${JSON.stringify(last, null, 2)}
\`\`\`
`;
}

function renderAcceptanceChecklist(gates: VerificationGate[]): string {
  return (
    gates
      .map((gate) => {
        const next = gate.nextAction === undefined ? "" : ` Next: ${gate.nextAction}`;
        return `- ${gate.status}: ${gate.label} - ${gate.detail} Evidence: ${gate.evidence}.${next}`;
      })
      .join("\n") + "\n"
  );
}

function renderRuntimeReadinessGates(gates: NonNullable<Live3dRuntimeSnapshot["readinessGates"]>): string {
  if (gates.length === 0) {
    return "- No runtime readiness gates were published.\n";
  }
  return gates.map((gate) => `- ${gate.state}: ${gate.label} - ${gate.detail}`).join("\n") + "\n";
}

function stepGate(
  id: string,
  label: string,
  result: VerificationResult,
  stepName: string,
): VerificationGate {
  const step = result.steps.find((candidate) => candidate.name === stepName);
  if (step === undefined) {
    return {
      id,
      label,
      status: "unknown",
      detail: `${stepName} did not run.`,
      evidence: "No matching verifier step was recorded",
    };
  }

  return {
    id,
    label,
    status: step.status === "passed" ? "passed" : step.status === "failed" ? "failed" : "unknown",
    detail: step.detail,
    evidence: `step "${step.name}" recorded ${step.status}`,
  };
}

function yoloArtifactGate(result: VerificationResult): VerificationGate {
  const snapshot = result.observation.lastSnapshot;
  if (snapshot === null) {
    return {
      id: "yolo-artifact",
      label: "YOLO artifact package",
      status: "unknown",
      detail: "No runtime snapshot was available.",
      evidence: "lastSnapshot is null",
    };
  }
  if (snapshot.yoloArtifact.status === "loaded") {
    return {
      id: "yolo-artifact",
      label: "YOLO artifact package",
      status: "passed",
      detail: `${snapshot.yoloArtifact.selectedModel ?? "unknown"} model loaded from ${snapshot.yoloArtifact.packagePath}.`,
      evidence: "lastSnapshot.yoloArtifact.status is loaded",
    };
  }
  return {
    id: "yolo-artifact",
    label: "YOLO artifact package",
    status: "failed",
    detail: snapshot.yoloArtifact.message ?? "YOLO artifact is not loaded.",
    evidence: `lastSnapshot.yoloArtifact.status is ${snapshot.yoloArtifact.status}`,
    nextAction: "Rebuild or verify artifacts/models/tennis_ball_yolo before testing cameras.",
  };
}

function calibrationArtifactGate(result: VerificationResult): VerificationGate {
  const snapshot = result.observation.lastSnapshot;
  if (snapshot === null) {
    return {
      id: "calibration-artifact",
      label: "Stereo calibration package",
      status: "unknown",
      detail: "No runtime snapshot was available.",
      evidence: "lastSnapshot is null",
    };
  }
  if (snapshot.calibrationArtifact.status === "loaded") {
    return {
      id: "calibration-artifact",
      label: "Stereo calibration package",
      status: "passed",
      detail: `baseline=${snapshot.calibrationArtifact.baselineMeters ?? "unknown"} m from ${snapshot.calibrationArtifact.packagePath}.`,
      evidence: "lastSnapshot.calibrationArtifact.status is loaded",
    };
  }
  return {
    id: "calibration-artifact",
    label: "Stereo calibration package",
    status: "failed",
    detail: snapshot.calibrationArtifact.message ?? "Stereo calibration artifact is not loaded.",
    evidence: `lastSnapshot.calibrationArtifact.status is ${snapshot.calibrationArtifact.status}`,
    nextAction: "Run the mono/stereo calibration flow and verify artifacts/calibration/stereo_cam1_cam2.",
  };
}

function cameraGateFromSnapshot(result: VerificationResult): VerificationGate {
  const snapshot = result.observation.lastSnapshot;
  if (snapshot === null) {
    return {
      id: "stereo-camera-streams",
      label: "Stereo USB camera streams",
      status: "unknown",
      detail: "No runtime snapshot was available.",
      evidence: "lastSnapshot is null",
    };
  }
  if (snapshot.camera.state === "ready" && snapshot.camera.deviceCount >= 2) {
    return {
      id: "stereo-camera-streams",
      label: "Stereo USB camera streams",
      status: "passed",
      detail: `${snapshot.camera.deviceCount} browser video input(s), left=${snapshot.camera.left.deviceLabel ?? "unknown"}, right=${snapshot.camera.right.deviceLabel ?? "unknown"}.`,
      evidence: "lastSnapshot.camera.state is ready",
    };
  }
  return {
    id: "stereo-camera-streams",
    label: "Stereo USB camera streams",
    status: "failed",
    detail: `${snapshot.camera.left.detail} ${snapshot.camera.right.detail}`,
    evidence: `lastSnapshot.camera.state is ${snapshot.camera.state}`,
    nextAction: "Check browser camera permission and that /dev/video0 and /dev/video2 are available.",
  };
}

function frameQualityGate(result: VerificationResult): VerificationGate {
  const savedCaptures = result.captures.filter((capture) => capture.status === "saved");
  const darkCaptures = savedCaptures.filter((capture) => (capture.maxLuma ?? 0) <= 8);
  if (savedCaptures.length >= 2 && darkCaptures.length === 0) {
    return {
      id: "frame-quality",
      label: "Readable camera frames",
      status: "passed",
      detail: `Saved ${savedCaptures.length} non-black browser frame capture(s).`,
      evidence: savedCaptures
        .map((capture) => `${capture.label} max_luma=${formatMetric(capture.maxLuma)}`)
        .join(", "),
    };
  }
  if (savedCaptures.length > 0 && darkCaptures.length > 0) {
    return {
      id: "frame-quality",
      label: "Readable camera frames",
      status: "failed",
      detail: `${darkCaptures.map((capture) => capture.label).join(", ")} capture(s) are near-black.`,
      evidence: savedCaptures
        .map((capture) => `${capture.label} max_luma=${formatMetric(capture.maxLuma)}`)
        .join(", "),
      nextAction: "Apply UVC controls, remove lens covers, and confirm lighting before judging YOLO.",
    };
  }
  return {
    id: "frame-quality",
    label: "Readable camera frames",
    status: "unknown",
    detail: "No complete left/right browser frame capture is available.",
    evidence:
      result.captures.length === 0
        ? "captures array is empty"
        : result.captures.map((capture) => `${capture.label}:${capture.status}`).join(", "),
  };
}

function detectionGate(
  id: string,
  label: string,
  maxDetections: number,
  yoloGate: VerificationGate,
  cameraGate: VerificationGate,
  frameGate: VerificationGate,
): VerificationGate {
  if (maxDetections > 0) {
    return {
      id,
      label,
      status: "passed",
      detail: `Observed ${maxDetections} tennis-ball detection(s) in at least one polled frame.`,
      evidence: `maxDetections=${maxDetections}`,
    };
  }

  const runtimeReadyForDetection =
    yoloGate.status === "passed" &&
    cameraGate.status === "passed" &&
    frameGate.status === "passed";
  if (runtimeReadyForDetection) {
    return {
      id,
      label,
      status: "blocked",
      detail: "The runtime was ready, but no tennis ball was visible to the detector.",
      evidence: "artifact, camera, and frame-quality gates passed with maxDetections=0",
      nextAction: "Put a visible tennis ball in both camera views or validate the model against the current lighting.",
    };
  }

  return {
    id,
    label,
    status: "unknown",
    detail: "Detection cannot be judged until the model, cameras, and readable frames are available.",
    evidence: `yolo=${yoloGate.status}, camera=${cameraGate.status}, frame=${frameGate.status}`,
  };
}

function triangulationGate(
  result: VerificationResult,
  calibrationGate: VerificationGate,
  leftDetectionGate: VerificationGate,
  rightDetectionGate: VerificationGate,
): VerificationGate {
  if (result.observation.maxTrailLength >= 1) {
    return {
      id: "stereo-triangulation",
      label: "Stereo triangulated ball point",
      status: "passed",
      detail: `Runtime trail reached ${result.observation.maxTrailLength} point(s).`,
      evidence: `maxTrailLength=${result.observation.maxTrailLength}`,
    };
  }
  if (
    calibrationGate.status === "passed" &&
    leftDetectionGate.status === "passed" &&
    rightDetectionGate.status === "passed"
  ) {
    return {
      id: "stereo-triangulation",
      label: "Stereo triangulated ball point",
      status: "failed",
      detail: "Both YOLO sides detected a ball, but no 3D point was triangulated.",
      evidence: `maxTrailLength=${result.observation.maxTrailLength}`,
      nextAction: "Check camera order, rectification quality, and stereo pairing thresholds.",
    };
  }
  return {
    id: "stereo-triangulation",
    label: "Stereo triangulated ball point",
    status: "unknown",
    detail: "Triangulation is waiting on calibration plus left/right detections.",
    evidence: `calibration=${calibrationGate.status}, left=${leftDetectionGate.status}, right=${rightDetectionGate.status}`,
  };
}

function predictionGate(result: VerificationResult): VerificationGate {
  if (
    result.observation.runtimeCodes.includes("prediction-ready") &&
    result.observation.maxPredictionSamples > 0
  ) {
    return {
      id: "trajectory-prediction",
      label: "Prediction curve and landing point",
      status: "passed",
      detail: `Prediction reached ${result.observation.maxPredictionSamples} sample(s).`,
      evidence: "runtimeCodes includes prediction-ready",
    };
  }
  if (result.observation.maxTrailLength === 1) {
    return {
      id: "trajectory-prediction",
      label: "Prediction curve and landing point",
      status: "blocked",
      detail: "Only one 3D ball point was observed; prediction needs two time-separated points.",
      evidence: "maxTrailLength=1",
      nextAction: "Move or throw the ball through both camera views for at least two frames.",
    };
  }
  if (result.observation.maxTrailLength >= 2) {
    return {
      id: "trajectory-prediction",
      label: "Prediction curve and landing point",
      status: "failed",
      detail: "Two or more 3D points were observed, but prediction-ready was not reached.",
      evidence: `maxTrailLength=${result.observation.maxTrailLength}, maxPredictionSamples=${result.observation.maxPredictionSamples}`,
      nextAction: "Inspect prediction input timing and trajectory solver diagnostics.",
    };
  }
  return {
    id: "trajectory-prediction",
    label: "Prediction curve and landing point",
    status: "unknown",
    detail: "Prediction is waiting on stereo triangulation.",
    evidence: `runtimeCodes=${result.observation.runtimeCodes.join(", ") || "none"}`,
  };
}

function formatMetric(value: number | undefined): string {
  return value === undefined ? "unknown" : value.toFixed(2);
}

function parseArgs(args: string[]): Options {
  let appUrl = process.env.LIVE3D_APP_URL ?? "http://localhost:5178";
  let timeoutMs = Number(process.env.LIVE3D_VERIFY_TIMEOUT_MS ?? defaultTimeoutMs);
  let pollMs = Number(process.env.LIVE3D_VERIFY_POLL_MS ?? defaultPollMs);
  let chromeDebugPort = Number(process.env.LIVE3D_CHROME_DEBUG_PORT ?? defaultChromeDebugPort);
  let chromeBin = process.env.CHROME_BIN;
  let keepChrome = false;
  let outputPath = defaultOutputPath(new Date());
  let captureDir = process.env.LIVE3D_VERIFY_CAPTURE_DIR;
  let prepareUvcControls = process.env.LIVE3D_VERIFY_PREPARE_UVC === "1";
  let uvcDevicePaths = (process.env.LIVE3D_VERIFY_UVC_DEVICES ?? "/dev/video0,/dev/video2")
    .split(",")
    .map((value) => value.trim())
    .filter((value) => value !== "");

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--app-url") {
      appUrl = requireValue(args, (index += 1), arg);
    } else if (arg === "--timeout-ms") {
      timeoutMs = Number(requireValue(args, (index += 1), arg));
    } else if (arg === "--poll-ms") {
      pollMs = Number(requireValue(args, (index += 1), arg));
    } else if (arg === "--chrome-debug-port") {
      chromeDebugPort = Number(requireValue(args, (index += 1), arg));
    } else if (arg === "--chrome-bin") {
      chromeBin = requireValue(args, (index += 1), arg);
    } else if (arg === "--keep-chrome") {
      keepChrome = true;
    } else if (arg === "--output") {
      outputPath = resolve(requireValue(args, (index += 1), arg));
    } else if (arg === "--capture-dir") {
      captureDir = resolve(requireValue(args, (index += 1), arg));
    } else if (arg === "--prepare-uvc-controls") {
      prepareUvcControls = true;
    } else if (arg === "--uvc-devices") {
      uvcDevicePaths = requireValue(args, (index += 1), arg)
        .split(",")
        .map((value) => value.trim())
        .filter((value) => value !== "");
    } else if (arg === "--help" || arg === "-h") {
      printHelp();
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }

  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error("--timeout-ms must be a positive number.");
  }
  if (!Number.isFinite(pollMs) || pollMs <= 0) {
    throw new Error("--poll-ms must be a positive number.");
  }
  if (!Number.isInteger(chromeDebugPort) || chromeDebugPort <= 0) {
    throw new Error("--chrome-debug-port must be a positive integer.");
  }
  if (prepareUvcControls && uvcDevicePaths.length === 0) {
    throw new Error("--uvc-devices must contain at least one device when --prepare-uvc-controls is used.");
  }

  return {
    appUrl,
    timeoutMs,
    pollMs,
    chromeDebugPort,
    chromeBin,
    keepChrome,
    outputPath,
    captureDir: captureDir ?? defaultCaptureDir(outputPath),
    prepareUvcControls,
    uvcDevicePaths,
  };
}

function requireValue(args: string[], index: number, flag: string): string {
  const value = args[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value.`);
  }
  return value;
}

function printHelp(): void {
  console.log(`用法: bun run verify:hardware [options]

默认值:
  --app-url                 http://localhost:5178
  --timeout-ms              ${defaultTimeoutMs}
  --poll-ms                 ${defaultPollMs}
  --chrome-debug-port       ${defaultChromeDebugPort}
  --output                  ${displayPath(defaultOutputPath(new Date()))}
  --capture-dir             <output>_frames
  --uvc-devices             /dev/video0,/dev/video2

选项:
  --app-url <url>              Live3D 页面地址。
  --timeout-ms <ms>            相机和运行时检查超时。
  --poll-ms <ms>               快照轮询间隔。
  --chrome-debug-port <port>   Chrome DevTools Protocol 端口。
  --chrome-bin <path>          Chrome/Chromium 可执行文件；也支持 CHROME_BIN。
  --keep-chrome                保留 Chrome 和 profile 目录，便于人工检查。
  --output <path>              Markdown 报告路径。
  --capture-dir <path>         左右视频 PNG 截图目录。
  --prepare-uvc-controls       启动 Chrome 前设置本机高亮度 UVC 参数。
  --uvc-devices <csv>          UVC 参数设置设备列表。
`);
}

function findChromeBinary(): string | undefined {
  const candidates = [
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
  ];
  for (const candidate of candidates) {
    const result = Bun.spawnSync(["which", candidate], { stdout: "pipe", stderr: "ignore" });
    if (result.exitCode === 0) {
      const path = result.stdout.toString().trim();
      if (path !== "" && existsSync(path)) {
        return path;
      }
    }
  }
  return undefined;
}

async function runCommand(command: string[], cwd: string): Promise<void> {
  const process = Bun.spawn(command, {
    cwd,
    stdout: "pipe",
    stderr: "pipe",
    stdin: "ignore",
  });
  const exitCode = await process.exited;
  if (exitCode !== 0) {
    throw new Error(`${command.join(" ")} failed with exit code ${exitCode}.`);
  }
}

async function isHttpOk(url: string): Promise<boolean> {
  try {
    const response = await fetch(url);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitUntil<T>(
  probe: () => Promise<T | undefined | false>,
  timeoutMs: number,
  pollMs: number,
): Promise<T> {
  const started = Date.now();
  while (Date.now() - started <= timeoutMs) {
    const result = await probe();
    if (result !== undefined && result !== false) {
      return result;
    }
    await sleep(pollMs);
  }
  throw new Error(`Timed out after ${timeoutMs} ms.`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolveSleep) => {
    setTimeout(resolveSleep, ms);
  });
}

function chromeDebugUrl(opts: Options, path: string): string {
  return `http://127.0.0.1:${opts.chromeDebugPort}${path}`;
}

function timestampForFilename(date: Date): string {
  return date.toISOString().replaceAll(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

function yyyymmdd(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function defaultOutputPath(date: Date): string {
  return resolve(
    repoRoot,
    "docs",
    "archive",
    yyyymmdd(date),
    "live3d",
    `live3d_hardware_loop_${timestampForFilename(date)}.md`,
  );
}

function displayPath(path: string): string {
  const resolvedRoot = resolve(repoRoot);
  const resolvedPath = resolve(path);
  return resolvedPath === resolvedRoot || !resolvedPath.startsWith(`${resolvedRoot}/`)
    ? path
    : resolvedPath.slice(resolvedRoot.length + 1);
}

function defaultCaptureDir(outputPath: string): string {
  const extension = extname(outputPath);
  const base = extension === "" ? outputPath : outputPath.slice(0, -extension.length);
  return `${base}_frames`;
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
