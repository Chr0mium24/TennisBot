import { defaultLive3dConfig, describeFixtureMode } from "./config";
import {
  attachCameraStream,
  createStereoCameraIdleStatus,
  createStereoCameraStartingStatus,
  startStereoCameraRuntime,
  stopStereoCameraRuntime,
  type CameraRuntimeStatus,
  type StereoCameraRuntimeStatus,
} from "./cameras";
import {
  BrowserFetchJsonReader,
  loadStereoCalibrationArtifactStatus,
  loadYoloArtifactStatus,
  type StereoCalibrationArtifactLoadStatus,
  type YoloArtifactLoadStatus,
} from "./artifacts";
import {
  createFixture,
  type CameraFixture,
  type Point3d,
} from "./fixtures";
import {
  createInitialRuntime3dState,
  updateRuntime3dState,
  type Runtime3dState,
} from "./runtime-scene";
import {
  createLive3dRuntimeSnapshot,
  type Live3dRuntimeSnapshot,
  createRuntimeReadinessGates,
  type RuntimeReadinessGate,
} from "./runtime-snapshot";
import {
  createBlockedYoloInferenceBackend,
  createStereoYoloInferenceIdleStatus,
  createYoloInferenceRunningStatus,
  detectionToOverlayBox,
  runYoloInferenceForFrame,
  type DetectionBox,
  type StereoYoloInferenceRuntimeStatus,
  type YoloInferenceBackend,
  type YoloInferenceRuntimeStatus,
} from "./detections";
import { OnnxYoloInferenceBackend } from "./onnx-yolo";
import "./styles.css";

declare global {
  interface Window {
    __tennisbotLive3dYoloBackend?: YoloInferenceBackend;
    __tennisbotLive3dSnapshot?: Live3dRuntimeSnapshot;
  }
}

const fixture = createFixture(defaultLive3dConfig);
const artifactReader = new BrowserFetchJsonReader();
const YOLO_LOOP_DELAY_MS = 250;

function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

function renderDetection(box: DetectionBox): string {
  const style = [
    `left:${box.x}%`,
    `top:${box.y}%`,
    `width:${box.width}%`,
    `height:${box.height}%`,
  ].join(";");

  return `
    <div class="detection-box" style="${style}">
      <span>${escapeHtml(box.label)} ${formatPercent(box.confidence)}</span>
    </div>
  `;
}

function renderCameraPanel(
  camera: CameraFixture,
  side: "left" | "right",
  detectionStatus: YoloInferenceRuntimeStatus,
): string {
  const configuredSize = defaultLive3dConfig.cameras[side].resolution;
  const imageSize = detectionStatus.imageSize ?? {
    widthPx: configuredSize.width,
    heightPx: configuredSize.height,
  };
  const runtimeBoxes =
    detectionStatus.state === "ready"
      ? detectionStatus.detections.map((detection) =>
          detectionToOverlayBox(detection, imageSize),
        )
      : [];
  const fixtureBoxes = camera.detections.map((detection) =>
    detectionToOverlayBox(detection, {
      widthPx: configuredSize.width,
      heightPx: configuredSize.height,
    }),
  );
  const boxes = runtimeBoxes.length > 0 ? runtimeBoxes : fixtureBoxes;
  const frameLabel =
    runtimeBoxes.length > 0
      ? `Runtime YOLO adapter detections from ${escapeHtml(detectionStatus.frameId ?? "current frame")}`
      : "Fixture detections overlay only; not YOLO validation";

  return `
    <section class="camera-panel" aria-label="${camera.name}">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">${side} live feed</p>
          <h2>${camera.name}</h2>
        </div>
        <span class="device-pill">${camera.frameLabel}</span>
      </div>
      <div class="camera-frame">
        <video
          id="${side}-camera-video"
          class="camera-video"
          aria-label="${side} USB camera video"
          muted
          autoplay
          playsinline
        ></video>
        <div class="frame-grid"></div>
        <div class="frame-horizon"></div>
        <div class="frame-label">${frameLabel}</div>
        ${boxes.map(renderDetection).join("")}
      </div>
    </section>
  `;
}

function projectPoint(x: number, z: number): { left: number; top: number } {
  return {
    left: 50 + x * 12,
    top: 78 - z * 7,
  };
}

function renderScene(runtime3dState: Runtime3dState): string {
  const hasRuntimeScene = runtime3dState.latestPoint !== null;
  const runtimeBall = runtime3dState.latestPoint ?? fixture.scene.ball;
  const scene = hasRuntimeScene
    ? {
        ball: runtimeBall,
        trail: runtime3dState.trail,
        prediction: runtime3dState.prediction,
        landing: runtime3dState.landingPoint,
        selectedPair: runtime3dState.selectedPair,
        eyebrow: "runtime 3D scene",
        title: runtime3dState.status.label,
        pill: runtime3dState.prediction?.model ?? "runtime triangulation",
      }
    : {
        ball: fixture.scene.ball,
        trail: fixture.scene.trail,
        prediction: fixture.scene.prediction,
        landing: fixture.scene.landing,
        selectedPair: fixture.selectedPair,
        eyebrow: "fixture-only fallback 3D scene",
        title: "Fixture ball trail and prediction; not runtime 3D validation",
        pill: fixture.scene.prediction.model,
      };
  const trailPoints = scene.trail.map((point) =>
    projectPoint(point.positionMeters.x, point.positionMeters.z),
  );
  const predictionPoints = scene.prediction?.samples.map((sample) =>
    projectPoint(sample.positionMeters.x, sample.positionMeters.z),
  ) ?? [];
  const landing =
    scene.landing === null
      ? null
      : projectPoint(scene.landing.positionMeters.x, scene.landing.positionMeters.z);
  const ball = projectPoint(
    scene.ball.positionMeters.x,
    scene.ball.positionMeters.z,
  );
  const toPolyline = (points: Array<{ left: number; top: number }>) =>
    points.map((point) => `${point.left},${point.top}`).join(" ");

  return `
    <section class="scene-panel" aria-label="${hasRuntimeScene ? "Runtime 3D scene" : "Fixture 3D fallback scene"}">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">${scene.eyebrow}</p>
          <h2>${escapeHtml(scene.title)}</h2>
        </div>
        <span class="device-pill">${escapeHtml(scene.pill)}</span>
      </div>
      <div class="scene-stage">
        <div class="court-plane"></div>
        <svg class="scene-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline class="trail-line" points="${toPolyline(trailPoints)}" />
          <polyline class="prediction-line" points="${toPolyline(predictionPoints)}" />
        </svg>
        ${
          landing === null
            ? ""
            : `<div class="landing-marker" style="left:${landing.left}%;top:${landing.top}%">landing</div>`
        }
        <div class="ball-marker" style="left:${ball.left}%;top:${ball.top}%"></div>
      </div>
      <dl class="scene-metrics">
        <div>
          <dt>match</dt>
          <dd>${escapeHtml(formatMatch(scene.selectedPair))}</dd>
        </div>
        <div>
          <dt>3D point</dt>
          <dd>${formatPoint(scene.ball.positionMeters)}</dd>
        </div>
        <div>
          <dt>landing</dt>
          <dd>${scene.landing === null ? "waiting for prediction landing" : formatPoint(scene.landing.positionMeters)}</dd>
        </div>
      </dl>
    </section>
  `;
}

function formatPoint(point: Point3d): string {
  return `${point.x.toFixed(2)}, ${point.y.toFixed(2)}, ${point.z.toFixed(2)} m`;
}

function renderStatusPanel(
  cameraStatus: StereoCameraRuntimeStatus,
  detectionStatus: StereoYoloInferenceRuntimeStatus,
  yoloStatus: YoloArtifactLoadStatus,
  calibrationStatus: StereoCalibrationArtifactLoadStatus,
  runtime3dState: Runtime3dState,
  yoloLoopActive: boolean,
): string {
  return `
    <aside class="status-panel" aria-label="Runtime status">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">status</p>
          <h2>Runtime readiness</h2>
        </div>
      </div>
      <div class="config-list">
        <div>
          <span>Left camera config</span>
          <strong>${formatCameraConfig(defaultLive3dConfig.cameras.left)}</strong>
        </div>
        <div>
          <span>Right camera config</span>
          <strong>${formatCameraConfig(defaultLive3dConfig.cameras.right)}</strong>
        </div>
        <div>
          <span>YOLO package</span>
          <strong>${defaultLive3dConfig.artifacts.yoloModelPackagePath}</strong>
        </div>
        <div>
          <span>Calibration package</span>
          <strong>${defaultLive3dConfig.artifacts.stereoCalibrationPackagePath}</strong>
        </div>
      </div>
      ${renderReadinessGates(
        createRuntimeReadinessGates({
          cameraStatus,
          detectionStatus,
          yoloStatus,
          calibrationStatus,
          runtime3dState,
          yoloLoopActive,
        }),
      )}
      ${renderCameraControls(cameraStatus)}
      <section class="camera-status" aria-label="Camera runtime status">
        ${renderCameraRuntimeStatus(cameraStatus.left)}
        ${renderCameraRuntimeStatus(cameraStatus.right)}
      </section>
      ${renderYoloControls(cameraStatus, detectionStatus, yoloStatus, yoloLoopActive)}
      <section class="camera-status" aria-label="YOLO inference runtime status">
        ${renderYoloInferenceRuntimeStatus(detectionStatus.left)}
        ${renderYoloInferenceRuntimeStatus(detectionStatus.right)}
      </section>
      <section class="artifact-status" aria-label="Artifact status">
        ${renderYoloArtifactStatus(yoloStatus)}
        ${renderCalibrationArtifactStatus(calibrationStatus)}
        ${renderRuntime3dStatus(runtime3dState)}
      </section>
      <ol class="status-list">
        ${fixture.status
          .map(
            (item) => `
              <li class="status-item status-${item.state}">
                <span class="status-dot"></span>
                <div>
                  <strong>${item.label}</strong>
                  <p>${item.detail}</p>
                </div>
              </li>
            `,
          )
          .join("")}
      </ol>
    </aside>
  `;
}

function renderReadinessGates(gates: RuntimeReadinessGate[]): string {
  return `
    <section class="readiness-gates" aria-label="Runtime readiness gates">
      ${gates
        .map(
          (gate) => `
            <article class="readiness-gate gate-${gate.state}">
              <span></span>
              <div>
                <strong>${escapeHtml(gate.label)}</strong>
                <p>${escapeHtml(gate.detail)}</p>
              </div>
            </article>
          `,
        )
        .join("")}
    </section>
  `;
}

function renderYoloControls(
  cameraStatus: StereoCameraRuntimeStatus,
  detectionStatus: StereoYoloInferenceRuntimeStatus,
  yoloStatus: YoloArtifactLoadStatus,
  yoloLoopActive: boolean,
): string {
  const isRunning =
    detectionStatus.left.state === "running" || detectionStatus.right.state === "running";
  const startDisabled =
    yoloLoopActive || isRunning || cameraStatus.state !== "ready" || yoloStatus.status !== "loaded";
  const stopDisabled =
    !yoloLoopActive && detectionStatus.left.state === "idle" && detectionStatus.right.state === "idle";

  return `
    <div class="camera-controls" aria-label="YOLO inference controls">
      <button id="yolo-start-button" type="button" ${startDisabled ? "disabled" : ""}>
        Start YOLO backend
      </button>
      <button id="yolo-stop-button" type="button" ${stopDisabled ? "disabled" : ""}>
        Stop YOLO adapter
      </button>
    </div>
  `;
}

function renderCameraControls(status: StereoCameraRuntimeStatus): string {
  const startDisabled = status.state === "pending" && status.left.code === "starting";
  const stopDisabled = status.state !== "ready";
  const startLabel =
    status.state === "ready"
      ? "Restart cameras"
      : status.state === "blocked"
        ? "Retry cameras"
        : "Start cameras";

  return `
    <div class="camera-controls" aria-label="Camera controls">
      <button id="camera-start-button" type="button" ${startDisabled ? "disabled" : ""}>
        ${startLabel}
      </button>
      <button id="camera-stop-button" type="button" ${stopDisabled ? "disabled" : ""}>
        Stop cameras
      </button>
    </div>
  `;
}

function formatCameraConfig(camera: (typeof defaultLive3dConfig.cameras)["left"]): string {
  const browserHints = [
    camera.deviceId === undefined ? undefined : `deviceId=${camera.deviceId}`,
    camera.labelMatch === undefined ? undefined : `label~${camera.labelMatch}`,
  ].filter((item): item is string => item !== undefined);
  return [
    camera.devicePath,
    `${camera.resolution.width}x${camera.resolution.height}@${camera.fps}`,
    ...browserHints,
  ].join(" ");
}

function renderCameraRuntimeStatus(status: CameraRuntimeStatus): string {
  return `
    <article class="runtime-card runtime-${status.state}">
      <h3>${escapeHtml(status.label)}</h3>
      <p>${escapeHtml(status.detail)}</p>
      ${
        status.deviceId === undefined
          ? ""
          : `<small>${escapeHtml(status.deviceLabel || status.deviceId)}</small>`
      }
    </article>
  `;
}

function renderYoloInferenceRuntimeStatus(status: YoloInferenceRuntimeStatus): string {
  const stateClass = status.state === "idle" ? "pending" : status.state;
  const warningText = status.warnings.length > 0 ? ` Warnings: ${status.warnings.join(" ")}` : "";

  return `
    <article class="runtime-card runtime-${stateClass}">
      <h3>${escapeHtml(status.label)}</h3>
      <p>${escapeHtml(`${status.detail}${warningText}`)}</p>
      <small>${escapeHtml(`${status.detectionCount} detection(s)`)}</small>
    </article>
  `;
}

function renderYoloArtifactStatus(status: YoloArtifactLoadStatus): string {
  if (status.status === "loaded") {
    const metadata = status.value;
    return renderArtifactCard({
      title: "YOLO artifact loaded",
      state: "ready",
      detail: [
        `Selected model: ${metadata.selectedModel}`,
        `Model path: ${metadata.modelPath}`,
        `Confidence threshold: ${formatPercent(metadata.confidenceThreshold)}`,
        `Pending checks: ${metadata.modelChecks
          .map((check) => `${check.kind} ${check.path}${check.expected === undefined ? "" : `=${check.expected}`}`)
          .join(", ")}`,
      ],
      warnings: status.warnings,
    });
  }

  return renderArtifactCard({
    title: "YOLO artifact blocked",
    state: "blocked",
    detail: status.errors.length > 0 ? status.errors : [status.message],
    warnings: status.warnings,
  });
}

function renderCalibrationArtifactStatus(status: StereoCalibrationArtifactLoadStatus): string {
  if (status.status === "loaded") {
    return renderArtifactCard({
      title: "Stereo calibration loaded",
      state: "ready",
      detail: [
        `Left camera: ${status.value.left.cameraId}`,
        `Right camera: ${status.value.right.cameraId}`,
        `Baseline: ${status.value.extrinsics.baselineMeters?.toFixed(3) ?? "unknown"} m`,
      ],
      warnings: status.warnings,
    });
  }

  return renderArtifactCard({
    title: "Stereo calibration blocked",
    state: "blocked",
    detail: status.errors.length > 0 ? status.errors : [status.message],
    warnings: status.warnings,
  });
}

function renderRuntime3dStatus(status: Runtime3dState): string {
  return `
    <article class="runtime-card runtime-${status.status.state}">
      <h3>${escapeHtml(status.status.label)}</h3>
      <p>${escapeHtml(status.status.detail)}</p>
      <small>${escapeHtml(`Trail points: ${status.trail.length}; selected pair: ${formatMatch(status.selectedPair)}`)}</small>
    </article>
  `;
}

function renderArtifactCard(options: {
  title: string;
  state: "ready" | "blocked";
  detail: string[];
  warnings: string[];
}): string {
  return `
    <article class="artifact-card artifact-${options.state}">
      <h3>${escapeHtml(options.title)}</h3>
      <ul>
        ${options.detail.map((line) => `<li>${escapeHtml(line)}</li>`).join("")}
      </ul>
      ${
        options.warnings.length > 0
          ? `<p class="artifact-warning">${escapeHtml(options.warnings.join(" "))}</p>`
          : ""
      }
    </article>
  `;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderApp(
  cameraStatus: StereoCameraRuntimeStatus,
  detectionStatus: StereoYoloInferenceRuntimeStatus,
  yoloStatus: YoloArtifactLoadStatus,
  calibrationStatus: StereoCalibrationArtifactLoadStatus,
  runtime3dState: Runtime3dState,
  yoloLoopActive: boolean,
): string {
  return `
    <main class="app-shell">
      <header class="top-bar">
        <div>
          <p class="eyebrow">TennisBot Live3D</p>
          <h1>Real-machine stereo runtime shell</h1>
        </div>
        <div class="mode-banner">${describeFixtureMode(defaultLive3dConfig.mode)}</div>
      </header>
      <section class="workspace">
        <div class="camera-grid">
          ${renderCameraPanel(fixture.cameras.left, "left", detectionStatus.left)}
          ${renderCameraPanel(fixture.cameras.right, "right", detectionStatus.right)}
          ${renderScene(runtime3dState)}
        </div>
        ${renderStatusPanel(cameraStatus, detectionStatus, yoloStatus, calibrationStatus, runtime3dState, yoloLoopActive)}
      </section>
    </main>
  `;
}

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing #app mount point");
}

const appElement = app;
const [yoloStatus, calibrationStatus] = await Promise.all([
  loadYoloArtifactStatus(artifactReader, defaultLive3dConfig.artifacts.yoloModelPackagePath),
  loadStereoCalibrationArtifactStatus(
    artifactReader,
    defaultLive3dConfig.artifacts.stereoCalibrationPackagePath,
  ),
]);
const yoloBackend =
  window.__tennisbotLive3dYoloBackend ?? createDefaultYoloBackend(yoloStatus);

let cameraStatus: StereoCameraRuntimeStatus = createStereoCameraIdleStatus(defaultLive3dConfig);
let detectionStatus: StereoYoloInferenceRuntimeStatus = createStereoYoloInferenceIdleStatus();
let runtime3dState: Runtime3dState = createInitialRuntime3dState();
let yoloRunSerial = 0;
let yoloLoopActive = false;
let yoloLoopTimeout: ReturnType<typeof globalThis.setTimeout> | undefined;

function renderCurrentApp(): void {
  publishRuntimeSnapshot();
  appElement.innerHTML = renderApp(
    cameraStatus,
    detectionStatus,
    yoloStatus,
    calibrationStatus,
    runtime3dState,
    yoloLoopActive,
  );
  bindCameraControls();
  bindYoloControls();
  attachReadyCameraStreams(cameraStatus);
}

function publishRuntimeSnapshot(): void {
  window.__tennisbotLive3dSnapshot = createLive3dRuntimeSnapshot({
    generatedAtUnixMs: Date.now(),
    cameraStatus,
    detectionStatus,
    yoloStatus,
    calibrationStatus,
    runtime3dState,
    yoloLoopActive,
  });
}

function bindCameraControls(): void {
  const startButton = document.querySelector<HTMLButtonElement>("#camera-start-button");
  const stopButton = document.querySelector<HTMLButtonElement>("#camera-stop-button");

  startButton?.addEventListener("click", () => {
    void startCameraRuntimeFromUserAction();
  });
  stopButton?.addEventListener("click", stopCameraRuntimeFromUserAction);
}

function bindYoloControls(): void {
  const startButton = document.querySelector<HTMLButtonElement>("#yolo-start-button");
  const stopButton = document.querySelector<HTMLButtonElement>("#yolo-stop-button");

  startButton?.addEventListener("click", () => {
    void startYoloInferenceFromUserAction();
  });
  stopButton?.addEventListener("click", () => {
    stopYoloInferenceFromUserAction();
    renderCurrentApp();
  });
}

async function startCameraRuntimeFromUserAction(): Promise<void> {
  stopStereoCameraRuntime(cameraStatus);
  stopYoloInferenceFromUserAction();
  cameraStatus = createStereoCameraStartingStatus(defaultLive3dConfig);
  renderCurrentApp();
  cameraStatus = await startStereoCameraRuntime(
    globalThis.navigator?.mediaDevices,
    defaultLive3dConfig,
  );
  renderCurrentApp();
}

function stopCameraRuntimeFromUserAction(): void {
  stopStereoCameraRuntime(cameraStatus);
  stopYoloInferenceFromUserAction();
  cameraStatus = createStereoCameraIdleStatus(defaultLive3dConfig);
  renderCurrentApp();
}

async function startYoloInferenceFromUserAction(): Promise<void> {
  if (cameraStatus.state !== "ready" || yoloStatus.status !== "loaded") {
    return;
  }

  const runSerial = yoloRunSerial + 1;
  yoloRunSerial = runSerial;
  yoloLoopActive = true;
  scheduleYoloInferenceIteration(runSerial, 0);
  renderCurrentApp();
}

async function runYoloInferenceIteration(runSerial: number): Promise<void> {
  if (runSerial !== yoloRunSerial || !yoloLoopActive || cameraStatus.state !== "ready") {
    return;
  }

  const timestampUnixMs = Date.now();
  const leftFrameId = `left-${timestampUnixMs}`;
  const rightFrameId = `right-${timestampUnixMs}`;
  detectionStatus = {
    left: createYoloInferenceRunningStatus("left", leftFrameId, timestampUnixMs),
    right: createYoloInferenceRunningStatus("right", rightFrameId, timestampUnixMs),
  };
  renderCurrentApp();

  const leftVideo = document.querySelector<HTMLVideoElement>("#left-camera-video");
  const rightVideo = document.querySelector<HTMLVideoElement>("#right-camera-video");

  const [left, right] = await Promise.all([
    runYoloInferenceForFrame(yoloBackend, {
      side: "left",
      cameraId: cameraStatus.left.deviceId ?? defaultLive3dConfig.cameras.left.id,
      frameId: leftFrameId,
      timestampUnixMs,
      imageSize: getVideoImageSize(leftVideo, defaultLive3dConfig.cameras.left.resolution),
      source: leftVideo,
    }),
    runYoloInferenceForFrame(yoloBackend, {
      side: "right",
      cameraId: cameraStatus.right.deviceId ?? defaultLive3dConfig.cameras.right.id,
      frameId: rightFrameId,
      timestampUnixMs,
      imageSize: getVideoImageSize(rightVideo, defaultLive3dConfig.cameras.right.resolution),
      source: rightVideo,
    }),
  ]);

  if (runSerial !== yoloRunSerial || !yoloLoopActive || cameraStatus.state !== "ready") {
    return;
  }

  detectionStatus = { left, right };
  runtime3dState = updateRuntime3dState({
    previousState: runtime3dState,
    left,
    right,
    calibrationStatus,
    frameId: `${leftFrameId}:${rightFrameId}`,
    timestampUnixMs,
  });
  renderCurrentApp();
  scheduleYoloInferenceIteration(runSerial, YOLO_LOOP_DELAY_MS);
}

function scheduleYoloInferenceIteration(runSerial: number, delayMs: number): void {
  if (runSerial !== yoloRunSerial || !yoloLoopActive) {
    return;
  }
  if (yoloLoopTimeout !== undefined) {
    globalThis.clearTimeout(yoloLoopTimeout);
  }
  yoloLoopTimeout = globalThis.setTimeout(() => {
    yoloLoopTimeout = undefined;
    void runYoloInferenceIteration(runSerial);
  }, delayMs);
}

function stopYoloInferenceFromUserAction(): void {
  yoloRunSerial += 1;
  yoloLoopActive = false;
  if (yoloLoopTimeout !== undefined) {
    globalThis.clearTimeout(yoloLoopTimeout);
    yoloLoopTimeout = undefined;
  }
  yoloBackend.stop?.();
  detectionStatus = createStereoYoloInferenceIdleStatus();
  runtime3dState = createInitialRuntime3dState();
}

function formatMatch(pair: Runtime3dState["selectedPair"]): string {
  if (pair === null) {
    return "none";
  }

  return `${pair.left.detectionId} / ${pair.right.detectionId}`;
}

function createDefaultYoloBackend(status: YoloArtifactLoadStatus): YoloInferenceBackend {
  if (status.status !== "loaded") {
    return createBlockedYoloInferenceBackend(
      `YOLO artifact is blocked; ONNX backend cannot start: ${status.message}`,
    );
  }

  return new OnnxYoloInferenceBackend({
    packagePath: status.packagePath,
    metadata: status.value,
  });
}

function getVideoImageSize(
  video: HTMLVideoElement | null,
  fallback: { width: number; height: number },
): { widthPx: number; heightPx: number } {
  return {
    widthPx: video?.videoWidth || fallback.width,
    heightPx: video?.videoHeight || fallback.height,
  };
}

function attachReadyCameraStreams(status: StereoCameraRuntimeStatus): void {
  if (status.state !== "ready") {
    return;
  }

  const leftVideo = document.querySelector<HTMLVideoElement>("#left-camera-video");
  const rightVideo = document.querySelector<HTMLVideoElement>("#right-camera-video");

  if (leftVideo !== null) {
    attachCameraStream(leftVideo, status.streams.left);
  }
  if (rightVideo !== null) {
    attachCameraStream(rightVideo, status.streams.right);
  }
}

renderCurrentApp();
