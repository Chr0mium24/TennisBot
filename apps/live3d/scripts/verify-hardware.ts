import { existsSync, mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";

import type { Live3dRuntimeSnapshot } from "../src/runtime-snapshot";

type Options = {
  appUrl: string;
  timeoutMs: number;
  pollMs: number;
  chromeDebugPort: number;
  chromeBin?: string;
  keepChrome: boolean;
  outputPath: string;
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

type VerificationResult = {
  status: "passed" | "failed" | "error";
  startedAt: Date;
  finishedAt: Date;
  appUrl: string;
  steps: VerificationStep[];
  observation: Observation;
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
      return failed(startedAt, opts, steps, observation, "YOLO artifact is blocked.");
    }
    if (initialSnapshot.calibrationArtifact.status !== "loaded") {
      return failed(startedAt, opts, steps, observation, "Stereo calibration artifact is blocked.");
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
      return failed(startedAt, opts, steps, observation, "Two real USB camera streams did not reach ready.");
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
      return failed(startedAt, opts, steps, observation, "Runtime 3D prediction did not reach ready.");
    }

    steps.push({
      name: "runtime 3D prediction",
      status: "passed",
      detail: `left max detections=${observation.maxLeftDetections}, right max detections=${observation.maxRightDetections}, trail=${observation.maxTrailLength}, samples=${observation.maxPredictionSamples}.`,
    });

    return {
      status: "passed",
      startedAt,
      finishedAt: new Date(),
      appUrl: opts.appUrl,
      steps,
      observation,
    };
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
    error,
  };
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

  return {
    appUrl,
    timeoutMs,
    pollMs,
    chromeDebugPort,
    chromeBin,
    keepChrome,
    outputPath,
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

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
