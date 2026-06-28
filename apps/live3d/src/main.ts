import { defaultLive3dConfig, describeFixtureMode } from "./config";
import {
  createFixture,
  detectionToBox,
  type CameraFixture,
  type DetectionBox,
  type Point3d,
} from "./fixtures";
import "./styles.css";

const fixture = createFixture(defaultLive3dConfig);

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
          <p class="eyebrow">${side} feed</p>
          <h2>${camera.name}</h2>
        </div>
        <span class="device-pill">${camera.frameLabel}</span>
      </div>
      <div class="camera-frame">
        <div class="frame-grid"></div>
        <div class="frame-horizon"></div>
        <div class="frame-label">USB camera frame placeholder</div>
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
          <p class="eyebrow">3D scene</p>
          <h2>Ball trail and prediction</h2>
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

function renderStatusPanel(): string {
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
          <span>Left camera</span>
          <strong>${defaultLive3dConfig.cameras.left.devicePath}</strong>
        </div>
        <div>
          <span>Right camera</span>
          <strong>${defaultLive3dConfig.cameras.right.devicePath}</strong>
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

function renderApp(): string {
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
        ${renderStatusPanel()}
      </section>
    </main>
  `;
}

const app = document.querySelector<HTMLDivElement>("#app");

if (!app) {
  throw new Error("Missing #app mount point");
}

app.innerHTML = renderApp();
