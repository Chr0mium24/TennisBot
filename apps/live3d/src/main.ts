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
  detectionToBox,
  type CameraFixture,
  type DetectionBox,
  type Point3d,
} from "./fixtures";
import "./styles.css";

const fixture = createFixture(defaultLive3dConfig);
const artifactReader = new BrowserFetchJsonReader();

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
      <span>${box.label} ${formatPercent(box.confidence)}</span>
    </div>
  `;
}

function renderCameraPanel(camera: CameraFixture, side: "left" | "right"): string {
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
        <div class="frame-label">Fixture detections overlay only; not YOLO validation</div>
        ${camera.detections.map(detectionToBox).map(renderDetection).join("")}
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

function renderScene(): string {
  const trailPoints = fixture.scene.trail.map((point) =>
    projectPoint(point.positionMeters.x, point.positionMeters.z),
  );
  const predictionPoints = fixture.scene.prediction.samples.map((sample) =>
    projectPoint(sample.positionMeters.x, sample.positionMeters.z),
  );
  const landing = projectPoint(
    fixture.scene.landing.positionMeters.x,
    fixture.scene.landing.positionMeters.z,
  );
  const ball = projectPoint(
    fixture.scene.ball.positionMeters.x,
    fixture.scene.ball.positionMeters.z,
  );
  const toPolyline = (points: Array<{ left: number; top: number }>) =>
    points.map((point) => `${point.left},${point.top}`).join(" ");

  return `
    <section class="scene-panel" aria-label="3D scene placeholder">
      <div class="panel-heading">
        <div>
          <p class="eyebrow">fixture-only non-validation 3D scene</p>
          <h2>Ball trail and prediction placeholder until YOLO inference is added</h2>
        </div>
        <span class="device-pill">${fixture.scene.prediction.model}</span>
      </div>
      <div class="scene-stage">
        <div class="court-plane"></div>
        <svg class="scene-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
          <polyline class="trail-line" points="${toPolyline(trailPoints)}" />
          <polyline class="prediction-line" points="${toPolyline(predictionPoints)}" />
        </svg>
        <div class="landing-marker" style="left:${landing.left}%;top:${landing.top}%">landing</div>
        <div class="ball-marker" style="left:${ball.left}%;top:${ball.top}%"></div>
      </div>
      <dl class="scene-metrics">
        <div>
          <dt>match</dt>
          <dd>${fixture.selectedPair.left.detectionId} / ${fixture.selectedPair.right.detectionId}</dd>
        </div>
        <div>
          <dt>3D point</dt>
          <dd>${formatPoint(fixture.scene.ball.positionMeters)}</dd>
        </div>
        <div>
          <dt>landing</dt>
          <dd>${formatPoint(fixture.scene.landing.positionMeters)}</dd>
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
  yoloStatus: YoloArtifactLoadStatus,
  calibrationStatus: StereoCalibrationArtifactLoadStatus,
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
      ${renderCameraControls(cameraStatus)}
      <section class="camera-status" aria-label="Camera runtime status">
        ${renderCameraRuntimeStatus(cameraStatus.left)}
        ${renderCameraRuntimeStatus(cameraStatus.right)}
      </section>
      <section class="artifact-status" aria-label="Artifact status">
        ${renderYoloArtifactStatus(yoloStatus)}
        ${renderCalibrationArtifactStatus(calibrationStatus)}
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
  yoloStatus: YoloArtifactLoadStatus,
  calibrationStatus: StereoCalibrationArtifactLoadStatus,
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
          ${renderCameraPanel(fixture.cameras.left, "left")}
          ${renderCameraPanel(fixture.cameras.right, "right")}
          ${renderScene()}
        </div>
        ${renderStatusPanel(cameraStatus, yoloStatus, calibrationStatus)}
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

let cameraStatus: StereoCameraRuntimeStatus = createStereoCameraIdleStatus(defaultLive3dConfig);

function renderCurrentApp(): void {
  appElement.innerHTML = renderApp(cameraStatus, yoloStatus, calibrationStatus);
  bindCameraControls();
  attachReadyCameraStreams(cameraStatus);
}

function bindCameraControls(): void {
  const startButton = document.querySelector<HTMLButtonElement>("#camera-start-button");
  const stopButton = document.querySelector<HTMLButtonElement>("#camera-stop-button");

  startButton?.addEventListener("click", () => {
    void startCameraRuntimeFromUserAction();
  });
  stopButton?.addEventListener("click", stopCameraRuntimeFromUserAction);
}

async function startCameraRuntimeFromUserAction(): Promise<void> {
  stopStereoCameraRuntime(cameraStatus);
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
  cameraStatus = createStereoCameraIdleStatus(defaultLive3dConfig);
  renderCurrentApp();
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
