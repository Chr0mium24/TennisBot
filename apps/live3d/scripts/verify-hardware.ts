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

type VerificationResult = {
  status: "passed" | "failed" | "error";
  startedAt: Date;
  finishedAt: Date;
  appUrl: string;
  steps: VerificationStep[];
  observation: Observation;
  captures: CaptureArtifact[];
  error?: string;
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

const options = parseArgs(Bun.argv.slice(2));
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

function renderReport(result: VerificationResult): string {
  const last = result.observation.lastSnapshot;
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

function parseArgs(args: string[]): Options {
  let appUrl = process.env.LIVE3D_APP_URL ?? "http://localhost:5178";
  let timeoutMs = Number(process.env.LIVE3D_VERIFY_TIMEOUT_MS ?? defaultTimeoutMs);
  let pollMs = Number(process.env.LIVE3D_VERIFY_POLL_MS ?? defaultPollMs);
  let chromeDebugPort = Number(process.env.LIVE3D_CHROME_DEBUG_PORT ?? defaultChromeDebugPort);
  let chromeBin = process.env.CHROME_BIN;
  let keepChrome = false;
  let outputPath = resolve(repoRoot, "docs", `live3d_hardware_loop_${timestampForFilename(new Date())}.md`);
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
  console.log(`Usage: bun run verify:hardware [options]

Options:
  --app-url <url>              Live3D app URL. Default: http://localhost:5178
  --timeout-ms <ms>            Timeout for camera and runtime checks. Default: ${defaultTimeoutMs}
  --poll-ms <ms>               Snapshot polling interval. Default: ${defaultPollMs}
  --chrome-debug-port <port>   Chrome DevTools Protocol port. Default: ${defaultChromeDebugPort}
  --chrome-bin <path>          Chrome/Chromium executable. Also supports CHROME_BIN.
  --keep-chrome                Leave Chrome and profile directory running for manual inspection.
  --output <path>              Markdown report path.
  --capture-dir <path>         Directory for left/right video PNG captures.
  --prepare-uvc-controls       Apply high-brightness UVC controls before launching Chrome.
  --uvc-devices <csv>          Device paths for UVC preparation. Default: /dev/video0,/dev/video2
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

function defaultCaptureDir(outputPath: string): string {
  const extension = extname(outputPath);
  const base = extension === "" ? outputPath : outputPath.slice(0, -extension.length);
  return `${base}_frames`;
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
