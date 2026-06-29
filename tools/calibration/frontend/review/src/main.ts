import {
  buildCaptureCommand,
  buildDetectCommand,
  buildInspectCommand,
  buildSolveCommand,
  classifyArtifact,
  frameRows,
  latest,
  observationRows,
  summarizeWorkflow,
  type CaptureCommandOptions,
  type ImportedArtifact,
  type JsonObject,
  type SolveCommandOptions,
} from "./calibration-workspace";

type Tab = "capture" | "review" | "solve" | "packages";

type AppState = {
  artifacts: ImportedArtifact[];
  activeTab: Tab;
  captureOptions: CaptureCommandOptions;
  solveOptions: SolveCommandOptions;
  sessionPath: string;
  observationsPath: string;
  inspectionReportPath: string;
  detectionReportPath: string;
};

const state: AppState = {
  artifacts: [],
  activeTab: "review",
  sessionPath: "../../artifacts/calibration_sessions/stereo_session",
  observationsPath: "../../artifacts/calibration_sessions/stereo_session/observations.json",
  inspectionReportPath: "../../docs/calibration_capture_quality_YYYYMMDD.md",
  detectionReportPath: "../../docs/calibration_charuco_detection_YYYYMMDD.md",
  captureOptions: {
    topology: "stereo",
    cameraId: "cam1",
    leftCameraId: "cam1",
    rightCameraId: "cam2",
    device: "/dev/video0",
    leftDevice: "/dev/video0",
    rightDevice: "/dev/video2",
    output: "../../artifacts/calibration_sessions/stereo_session",
    frameCount: 20,
    pairCount: 20,
    width: 1280,
    height: 720,
    intervalMs: 500,
    prepareUvcControls: true,
  },
  solveOptions: {
    topology: "stereo",
    observations: "../../artifacts/calibration_sessions/stereo_session/observations.json",
    output: "../../artifacts/calibration/stereo_cam1_cam2",
    cameraId: "cam1",
    leftMono: "../../artifacts/calibration/cam1",
    rightMono: "../../artifacts/calibration/cam2",
    minViews: 8,
    minPairs: 12,
    maxRmsPx: 2,
  },
};

const app = document.querySelector<HTMLDivElement>("#app");
if (app === null) {
  throw new Error("App root not found.");
}

render();

function render(): void {
  const inspection = latest(state.artifacts, "captureInspection")?.payload;
  const observations = latest(state.artifacts, "charucoObservations")?.payload;
  const monoPackage = latest(state.artifacts, "monoPackage")?.payload;
  const stereoPackage = latest(state.artifacts, "stereoPackage")?.payload;
  app.innerHTML = `
    <section class="shell">
      <aside class="sidebar">
        <div class="brand">
          <div>
            <h1>TennisBot Calibration</h1>
            <p>Review workspace</p>
          </div>
        </div>
        <label class="file-drop" id="drop-zone">
          <span class="file-drop-title">Import JSON</span>
          <span class="file-drop-detail">manifest, inspection, observations, package</span>
          <input id="file-input" type="file" accept="application/json,.json" multiple>
        </label>
        <div class="stage-list">
          ${summarizeWorkflow(state.artifacts).map(renderStage).join("")}
        </div>
      </aside>
      <section class="workspace">
        <header class="toolbar">
          <div class="tabs">
            ${renderTab("review", "Review")}
            ${renderTab("capture", "Capture")}
            ${renderTab("solve", "Solve")}
            ${renderTab("packages", "Packages")}
          </div>
          <button class="secondary" id="load-sample">Load Sample</button>
        </header>
        ${state.activeTab === "capture" ? renderCapturePanel() : ""}
        ${state.activeTab === "review" ? renderReviewPanel(inspection, observations) : ""}
        ${state.activeTab === "solve" ? renderSolvePanel() : ""}
        ${state.activeTab === "packages" ? renderPackagesPanel(monoPackage, stereoPackage) : ""}
      </section>
    </section>
  `;
  wireEvents();
}

function renderStage(stage: ReturnType<typeof summarizeWorkflow>[number]): string {
  return `
    <article class="stage ${stage.state}">
      <div>
        <strong>${escapeHtml(stage.label)}</strong>
        <p>${escapeHtml(stage.detail)}</p>
      </div>
      <span>${escapeHtml(stage.metric ?? stage.state)}</span>
    </article>
  `;
}

function renderTab(tab: Tab, label: string): string {
  return `<button class="tab ${state.activeTab === tab ? "active" : ""}" data-tab="${tab}">${label}</button>`;
}

function renderCapturePanel(): string {
  return `
    <section class="panel-grid">
      <article class="panel">
        <h2>Capture</h2>
        <div class="segmented">
          <button class="${state.captureOptions.topology === "mono" ? "active" : ""}" data-capture-topology="mono">Mono</button>
          <button class="${state.captureOptions.topology === "stereo" ? "active" : ""}" data-capture-topology="stereo">Stereo</button>
        </div>
        <div class="form-grid">
          ${field("cameraId", "Camera", state.captureOptions.cameraId, state.captureOptions.topology === "mono")}
          ${field("leftCameraId", "Left", state.captureOptions.leftCameraId, state.captureOptions.topology === "stereo")}
          ${field("rightCameraId", "Right", state.captureOptions.rightCameraId, state.captureOptions.topology === "stereo")}
          ${field("device", "Device", state.captureOptions.device, state.captureOptions.topology === "mono")}
          ${field("leftDevice", "Left device", state.captureOptions.leftDevice, state.captureOptions.topology === "stereo")}
          ${field("rightDevice", "Right device", state.captureOptions.rightDevice, state.captureOptions.topology === "stereo")}
          ${field("output", "Output", state.captureOptions.output, true)}
          ${numberField("frameCount", "Frames", state.captureOptions.frameCount, state.captureOptions.topology === "mono")}
          ${numberField("pairCount", "Pairs", state.captureOptions.pairCount, state.captureOptions.topology === "stereo")}
          ${numberField("width", "Width", state.captureOptions.width, true)}
          ${numberField("height", "Height", state.captureOptions.height, true)}
          ${numberField("intervalMs", "Interval ms", state.captureOptions.intervalMs, true)}
        </div>
        <label class="toggle">
          <input id="prepare-uvc" type="checkbox" ${state.captureOptions.prepareUvcControls ? "checked" : ""}>
          <span>Prepare UVC controls</span>
        </label>
      </article>
      <article class="panel command-panel">
        <h2>Commands</h2>
        ${commandBlock(buildCaptureCommand(state.captureOptions))}
        ${commandBlock(buildInspectCommand(state.sessionPath, state.inspectionReportPath))}
        ${commandBlock(buildDetectCommand(state.sessionPath, state.observationsPath, state.detectionReportPath))}
      </article>
    </section>
  `;
}

function renderReviewPanel(inspection: JsonObject | undefined, observations: JsonObject | undefined): string {
  return `
    <section class="panel-stack">
      <article class="panel">
        <h2>Capture Quality</h2>
        ${renderTable(["path", "side", "status", "luma", "contrast", "issues"], frameRows(inspection))}
      </article>
      <article class="panel">
        <h2>ChArUco Observations</h2>
        ${renderTable(["path", "side", "accepted", "corners", "markers", "reason"], observationRows(observations))}
      </article>
    </section>
  `;
}

function renderSolvePanel(): string {
  return `
    <section class="panel-grid">
      <article class="panel">
        <h2>Solve</h2>
        <div class="segmented">
          <button class="${state.solveOptions.topology === "mono" ? "active" : ""}" data-solve-topology="mono">Mono</button>
          <button class="${state.solveOptions.topology === "stereo" ? "active" : ""}" data-solve-topology="stereo">Stereo</button>
        </div>
        <div class="form-grid">
          ${solveField("observations", "Observations", state.solveOptions.observations, true)}
          ${solveField("output", "Output", state.solveOptions.output, true)}
          ${solveField("cameraId", "Camera", state.solveOptions.cameraId, state.solveOptions.topology === "mono")}
          ${solveField("leftMono", "Left mono", state.solveOptions.leftMono, state.solveOptions.topology === "stereo")}
          ${solveField("rightMono", "Right mono", state.solveOptions.rightMono, state.solveOptions.topology === "stereo")}
          ${solveNumberField("minViews", "Min views", state.solveOptions.minViews, state.solveOptions.topology === "mono")}
          ${solveNumberField("minPairs", "Min pairs", state.solveOptions.minPairs, state.solveOptions.topology === "stereo")}
          ${solveNumberField("maxRmsPx", "Max RMS px", state.solveOptions.maxRmsPx, true)}
        </div>
      </article>
      <article class="panel command-panel">
        <h2>Command</h2>
        ${commandBlock(buildSolveCommand(state.solveOptions))}
      </article>
    </section>
  `;
}

function renderPackagesPanel(monoPackage: JsonObject | undefined, stereoPackage: JsonObject | undefined): string {
  return `
    <section class="panel-grid">
      <article class="panel">
        <h2>Mono Package</h2>
        ${packageMetrics(monoPackage, ["camera_id", "accepted", "dry_run", "hardware_validated"])}
      </article>
      <article class="panel">
        <h2>Stereo Package</h2>
        ${packageMetrics(stereoPackage, ["camera_ids", "accepted", "dry_run", "hardware_validated"])}
      </article>
    </section>
  `;
}

function packageMetrics(payload: JsonObject | undefined, keys: string[]): string {
  if (payload === undefined) return `<p class="empty">No package loaded.</p>`;
  const quality = payload.quality && typeof payload.quality === "object" ? (payload.quality as JsonObject) : {};
  const rows = [
    ...keys.map((key) => [key, display(payload[key])]),
    ...Object.entries(quality).map(([key, value]) => [`quality.${key}`, display(value)]),
  ];
  return `<dl class="metrics">${rows.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>`;
}

function renderTable(columns: string[], rows: Array<Record<string, string>>): string {
  if (rows.length === 0) return `<p class="empty">No rows loaded.</p>`;
  return `
    <div class="table-wrap">
      <table>
        <thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows
            .map((row) => `<tr>${columns.map((column) => `<td>${escapeHtml(row[column] ?? "-")}</td>`).join("")}</tr>`)
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function commandBlock(command: string): string {
  return `<pre><code>${escapeHtml(command)}</code></pre>`;
}

function field(key: keyof CaptureCommandOptions, label: string, value: string, visible: boolean): string {
  return visible ? `<label>${label}<input data-capture-field="${key}" value="${escapeHtml(value)}"></label>` : "";
}

function numberField(key: keyof CaptureCommandOptions, label: string, value: number, visible: boolean): string {
  return visible ? `<label>${label}<input data-capture-field="${key}" type="number" value="${value}"></label>` : "";
}

function solveField(key: keyof SolveCommandOptions, label: string, value: string, visible: boolean): string {
  return visible ? `<label>${label}<input data-solve-field="${key}" value="${escapeHtml(value)}"></label>` : "";
}

function solveNumberField(key: keyof SolveCommandOptions, label: string, value: number, visible: boolean): string {
  return visible ? `<label>${label}<input data-solve-field="${key}" type="number" step="0.1" value="${value}"></label>` : "";
}

function wireEvents(): void {
  document.querySelectorAll<HTMLButtonElement>("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.activeTab = button.dataset.tab as Tab;
      render();
    });
  });
  document.querySelector("#file-input")?.addEventListener("change", (event) => {
    const input = event.currentTarget as HTMLInputElement;
    void importFiles(input.files);
  });
  document.querySelector("#drop-zone")?.addEventListener("dragover", (event) => event.preventDefault());
  document.querySelector("#drop-zone")?.addEventListener("drop", (event) => {
    event.preventDefault();
    void importFiles((event as DragEvent).dataTransfer?.files ?? null);
  });
  document.querySelector("#load-sample")?.addEventListener("click", () => {
    state.artifacts = sampleArtifacts();
    render();
  });
  document.querySelectorAll<HTMLButtonElement>("[data-capture-topology]").forEach((button) => {
    button.addEventListener("click", () => {
      state.captureOptions.topology = button.dataset.captureTopology as CaptureCommandOptions["topology"];
      render();
    });
  });
  document.querySelectorAll<HTMLInputElement>("[data-capture-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.captureField as keyof CaptureCommandOptions;
      (state.captureOptions[key] as string | number) = input.type === "number" ? Number(input.value) : input.value;
      if (key === "output") state.sessionPath = input.value;
      render();
    });
  });
  document.querySelector<HTMLInputElement>("#prepare-uvc")?.addEventListener("change", (event) => {
    state.captureOptions.prepareUvcControls = (event.currentTarget as HTMLInputElement).checked;
    render();
  });
  document.querySelectorAll<HTMLButtonElement>("[data-solve-topology]").forEach((button) => {
    button.addEventListener("click", () => {
      state.solveOptions.topology = button.dataset.solveTopology as SolveCommandOptions["topology"];
      render();
    });
  });
  document.querySelectorAll<HTMLInputElement>("[data-solve-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.solveField as keyof SolveCommandOptions;
      (state.solveOptions[key] as string | number) = input.type === "number" ? Number(input.value) : input.value;
      render();
    });
  });
}

async function importFiles(files: FileList | null): Promise<void> {
  if (files === null) return;
  for (const file of Array.from(files)) {
    const text = await file.text();
    const payload = JSON.parse(text) as JsonObject;
    state.artifacts.push({
      id: `${file.name}:${Date.now()}`,
      name: file.name,
      kind: classifyArtifact(payload),
      payload,
    });
  }
  render();
}

function sampleArtifacts(): ImportedArtifact[] {
  return [
    {
      id: "sample-manifest",
      name: "manifest.json",
      kind: "captureManifest",
      payload: { schema_version: "calibration.capture_session.v1", topology: "stereo", session_id: "sample_stereo", pair_count: 5 },
    },
    {
      id: "sample-inspection",
      name: "inspection.json",
      kind: "captureInspection",
      payload: {
        schema_version: "calibration.capture_inspection.v1",
        accepted: true,
        read_image_count: 10,
        image_count: 10,
        frames: [{ path: "frames/cam1_0001.png", side: "left", status: "read", mean_luma: 159.527, std_luma: 121.506, issues: [] }],
      },
    },
    {
      id: "sample-observations",
      name: "observations.json",
      kind: "charucoObservations",
      payload: {
        schema_version: "calibration.charuco_observations.v1",
        accepted: true,
        topology: "stereo",
        accepted_view_count: 10,
        total_view_count: 10,
        accepted_pair_count: 5,
        total_pair_count: 5,
        views: [{ path: "frames/cam1_0001.png", side: "left", accepted: true, corner_count: 104, marker_count: 63 }],
      },
    },
  ];
}

function display(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return String(Number(value.toFixed(6)));
  if (typeof value === "boolean") return String(value);
  return typeof value === "string" ? value : "-";
}

function escapeHtml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
