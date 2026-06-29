import {
  buildCaptureCommand,
  buildDetectCommand,
  buildInspectCommand,
  buildSolveCommand,
  buildTargetCommand,
  buildVerifyCommand,
  captureFramePreviews,
  classifyArtifact,
  frameRows,
  latest,
  observationRows,
  summarizeWorkflow,
  type CaptureCommandOptions,
  type ImportedArtifact,
  type JsonObject,
  type SolveCommandOptions,
  type TargetCommandOptions,
} from "./calibration-workspace";

type Tab = "target" | "capture" | "review" | "solve" | "packages";
type CommandId = "target" | "capture" | "inspect" | "detect" | "solve" | "verify";
type FlowPreset = "cam1Mono" | "cam2Mono" | "stereo";

type CommandRunView = {
  status: "running" | "passed" | "failed" | "rejected" | "error";
  detail: string;
  stdout: string;
  stderr: string;
};

type AppState = {
  artifacts: ImportedArtifact[];
  activeTab: Tab;
  activePreset: FlowPreset;
  targetOptions: TargetCommandOptions;
  captureOptions: CaptureCommandOptions;
  solveOptions: SolveCommandOptions;
  sessionPath: string;
  observationsPath: string;
  inspectionReportPath: string;
  detectionReportPath: string;
  verifyPath: string;
  commandRuns: Partial<Record<CommandId, CommandRunView>>;
};

const state: AppState = {
  artifacts: [],
  activeTab: "target",
  activePreset: "stereo",
  sessionPath: "../../artifacts/calibration_sessions/stereo_session",
  observationsPath: "../../artifacts/calibration_sessions/stereo_session/observations.json",
  inspectionReportPath: "../../docs/calibration_capture_quality_YYYYMMDD.md",
  detectionReportPath: "../../docs/calibration_charuco_detection_YYYYMMDD.md",
  verifyPath: "../../artifacts/calibration/stereo_cam1_cam2",
  commandRuns: {},
  targetOptions: {
    output: "../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png",
    outputReport: "../../docs/calibration_charuco_target_sheet_YYYYMMDD.md",
    dpi: 300,
    marginMm: 10,
  },
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
  const targetSheet = latest(state.artifacts, "targetSheet")?.payload;
  const manifest = latest(state.artifacts, "captureManifest")?.payload;
  const inspection = latest(state.artifacts, "captureInspection")?.payload;
  const observations = latest(state.artifacts, "charucoObservations")?.payload;
  const monoPackage = latest(state.artifacts, "monoPackage")?.payload;
  const stereoPackage = latest(state.artifacts, "stereoPackage")?.payload;
  const packageVerification = latest(state.artifacts, "packageVerification")?.payload;
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
            ${renderTab("target", "Target")}
            ${renderTab("review", "Review")}
            ${renderTab("capture", "Capture")}
            ${renderTab("solve", "Solve")}
            ${renderTab("packages", "Packages")}
          </div>
          <div class="preset-switch">
            ${renderPresetButton("cam1Mono", "Cam1 Mono")}
            ${renderPresetButton("cam2Mono", "Cam2 Mono")}
            ${renderPresetButton("stereo", "Stereo")}
          </div>
          <button class="secondary" id="load-sample">Load Sample</button>
        </header>
        ${state.activeTab === "target" ? renderTargetPanel(targetSheet) : ""}
        ${state.activeTab === "capture" ? renderCapturePanel() : ""}
        ${state.activeTab === "review" ? renderReviewPanel(manifest, inspection, observations) : ""}
        ${state.activeTab === "solve" ? renderSolvePanel() : ""}
        ${state.activeTab === "packages" ? renderPackagesPanel(monoPackage, stereoPackage, packageVerification) : ""}
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

function renderPresetButton(preset: FlowPreset, label: string): string {
  return `<button class="${state.activePreset === preset ? "active" : ""}" data-flow-preset="${preset}">${label}</button>`;
}

function renderTargetPanel(targetSheet: JsonObject | undefined): string {
  return `
    <section class="panel-grid">
      <article class="panel">
        <h2>Target</h2>
        <div class="form-grid">
          ${targetField("output", "Output", state.targetOptions.output)}
          ${targetField("outputReport", "Report", state.targetOptions.outputReport)}
          ${targetNumberField("dpi", "DPI", state.targetOptions.dpi)}
          ${targetNumberField("marginMm", "Margin mm", state.targetOptions.marginMm)}
        </div>
      </article>
      <article class="panel command-panel">
        <h2>Command</h2>
        ${commandBlock("target", "Generate target", buildCommand("target"))}
      </article>
      <article class="panel">
        <h2>Target Sheet</h2>
        ${targetSheetMetrics(targetSheet)}
      </article>
    </section>
  `;
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
        ${commandBlock("capture", "Capture frames", buildCommand("capture"))}
        ${commandBlock("inspect", "Inspect frames", buildCommand("inspect"))}
        ${commandBlock("detect", "Detect ChArUco", buildCommand("detect"))}
      </article>
    </section>
  `;
}

function renderReviewPanel(
  manifest: JsonObject | undefined,
  inspection: JsonObject | undefined,
  observations: JsonObject | undefined,
): string {
  const previews = captureFramePreviews(manifest, inspection);
  return `
    <section class="panel-stack">
      <article class="panel">
        <h2>Frame Preview</h2>
        ${renderFramePreviewGallery(previews)}
      </article>
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

function renderFramePreviewGallery(previews: ReturnType<typeof captureFramePreviews>): string {
  if (previews.length === 0) return `<p class="empty">No capture frames loaded.</p>`;
  return `
    <div class="frame-gallery">
      ${previews
        .map(
          (preview) => `
            <article class="frame-card">
              <div class="frame-media">
                ${
                  preview.imageUrl === undefined
                    ? `<span>No local preview URL</span>`
                    : `<img src="${escapeHtml(preview.imageUrl)}" alt="${escapeHtml(preview.side)} ${escapeHtml(preview.path)}" loading="lazy">`
                }
              </div>
              <div class="frame-meta">
                <strong>${escapeHtml(preview.side)} ${escapeHtml(preview.index)}</strong>
                <span>${escapeHtml(preview.cameraId)} &middot; ${escapeHtml(preview.status)}</span>
                <span>${escapeHtml(preview.size)} &middot; luma ${escapeHtml(preview.luma)} &middot; contrast ${escapeHtml(preview.contrast)}</span>
                <span>${escapeHtml(preview.issues)}</span>
                <code>${escapeHtml(preview.path)}</code>
              </div>
            </article>
          `,
        )
        .join("")}
    </div>
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
        ${commandBlock("solve", "Run solve", buildCommand("solve"))}
      </article>
    </section>
  `;
}

function renderPackagesPanel(
  monoPackage: JsonObject | undefined,
  stereoPackage: JsonObject | undefined,
  packageVerification: JsonObject | undefined,
): string {
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
      <article class="panel command-panel">
        <h2>Verify</h2>
        ${verifyField("verifyPath", "Package", state.verifyPath)}
        ${commandBlock("verify", "Verify package", buildCommand("verify"))}
      </article>
      <article class="panel">
        <h2>Verification</h2>
        ${verificationMetrics(packageVerification)}
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

function targetSheetMetrics(payload: JsonObject | undefined): string {
  if (payload === undefined) return `<p class="empty">No target sheet loaded.</p>`;
  const target = payload.target && typeof payload.target === "object" && !Array.isArray(payload.target) ? (payload.target as JsonObject) : {};
  const board =
    payload.board_size_mm && typeof payload.board_size_mm === "object" && !Array.isArray(payload.board_size_mm)
      ? (payload.board_size_mm as JsonObject)
      : {};
  const rows = [
    ["accepted", display(payload.accepted)],
    ["profile", display(target.profile)],
    ["dictionary", display(target.dictionary)],
    ["squares", `${display(target.squares_x)} x ${display(target.squares_y)}`],
    ["square_mm", display(typeof target.square_size_m === "number" ? target.square_size_m * 1000 : undefined)],
    ["board_mm", `${display(board.width)} x ${display(board.height)}`],
    ["dpi", display(payload.dpi)],
  ];
  return `<dl class="metrics">${rows.map(([key, value]) => `<dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value)}</dd>`).join("")}</dl>`;
}

function verificationMetrics(payload: JsonObject | undefined): string {
  if (payload === undefined) return `<p class="empty">No verification loaded.</p>`;
  const rows = [
    ["accepted", display(payload.accepted)],
    ["package_kind", display(payload.package_kind)],
    ["package_dir", display(payload.package_dir)],
    ["dry_run", display(payload.dry_run)],
    ["hardware_validated", display(payload.hardware_validated)],
    ["details", Array.isArray(payload.details) ? payload.details.join(", ") : display(payload.details)],
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

function commandBlock(id: CommandId, label: string, command: string): string {
  const run = state.commandRuns[id];
  const running = run?.status === "running";
  return `
    <div class="command-block">
      <div class="command-header">
        <strong>${escapeHtml(label)}</strong>
        <button class="run-command" data-run-command-id="${id}" ${running ? "disabled" : ""}>
          ${running ? "Running" : "Run"}
        </button>
      </div>
      <pre><code>${escapeHtml(command)}</code></pre>
      ${run === undefined ? "" : renderCommandRun(run)}
    </div>
  `;
}

function renderCommandRun(run: CommandRunView): string {
  return `
    <div class="command-result ${run.status}">
      <strong>${escapeHtml(run.status)}</strong>
      <span>${escapeHtml(run.detail)}</span>
      ${run.stdout === "" ? "" : `<pre><code>${escapeHtml(run.stdout)}</code></pre>`}
      ${run.stderr === "" ? "" : `<pre><code>${escapeHtml(run.stderr)}</code></pre>`}
    </div>
  `;
}

function buildCommand(id: CommandId): string {
  if (id === "target") return buildTargetCommand(state.targetOptions);
  if (id === "capture") return buildCaptureCommand(state.captureOptions);
  if (id === "inspect") return buildInspectCommand(state.sessionPath, state.inspectionReportPath);
  if (id === "detect") return buildDetectCommand(state.sessionPath, state.observationsPath, state.detectionReportPath);
  if (id === "verify") return buildVerifyCommand(state.verifyPath);
  return buildSolveCommand(state.solveOptions);
}

function targetField(key: keyof TargetCommandOptions, label: string, value: string | number): string {
  return `<label>${label}<input data-target-field="${key}" value="${escapeHtml(String(value))}"></label>`;
}

function targetNumberField(key: keyof TargetCommandOptions, label: string, value: number): string {
  return `<label>${label}<input data-target-field="${key}" type="number" step="0.1" value="${value}"></label>`;
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

function verifyField(key: "verifyPath", label: string, value: string): string {
  return `<label>${label}<input data-verify-field="${key}" value="${escapeHtml(value)}"></label>`;
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
  document.querySelectorAll<HTMLButtonElement>("[data-flow-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      applyFlowPreset(button.dataset.flowPreset as FlowPreset);
      render();
    });
  });
  document.querySelectorAll<HTMLInputElement>("[data-target-field]").forEach((input) => {
    input.addEventListener("input", () => {
      const key = input.dataset.targetField as keyof TargetCommandOptions;
      (state.targetOptions[key] as string | number) = input.type === "number" ? Number(input.value) : input.value;
      render();
    });
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
      if (key === "output") updateSessionPaths(input.value);
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
      if (key === "output") state.verifyPath = input.value;
      if (key === "observations") state.observationsPath = input.value;
      render();
    });
  });
  document.querySelectorAll<HTMLInputElement>("[data-verify-field]").forEach((input) => {
    input.addEventListener("input", () => {
      state.verifyPath = input.value;
      render();
    });
  });
  document.querySelectorAll<HTMLButtonElement>("[data-run-command-id]").forEach((button) => {
    button.addEventListener("click", () => {
      const id = button.dataset.runCommandId as CommandId;
      void runCalibrationCommand(id);
    });
  });
}

function applyFlowPreset(preset: FlowPreset): void {
  state.activePreset = preset;
  if (preset === "cam1Mono") {
    applyMonoPreset({
      cameraId: "cam1",
      device: "/dev/video0",
      session: "../../artifacts/calibration_sessions/cam1_session",
      packagePath: "../../artifacts/calibration/cam1",
      inspectReport: "../../docs/calibration_capture_quality_cam1_YYYYMMDD.md",
      detectReport: "../../docs/calibration_charuco_detection_cam1_YYYYMMDD.md",
    });
    return;
  }
  if (preset === "cam2Mono") {
    applyMonoPreset({
      cameraId: "cam2",
      device: "/dev/video2",
      session: "../../artifacts/calibration_sessions/cam2_session",
      packagePath: "../../artifacts/calibration/cam2",
      inspectReport: "../../docs/calibration_capture_quality_cam2_YYYYMMDD.md",
      detectReport: "../../docs/calibration_charuco_detection_cam2_YYYYMMDD.md",
    });
    return;
  }

  const session = "../../artifacts/calibration_sessions/stereo_session";
  const packagePath = "../../artifacts/calibration/stereo_cam1_cam2";
  state.captureOptions = {
    ...state.captureOptions,
    topology: "stereo",
    leftCameraId: "cam1",
    rightCameraId: "cam2",
    leftDevice: "/dev/video0",
    rightDevice: "/dev/video2",
    output: session,
  };
  state.solveOptions = {
    ...state.solveOptions,
    topology: "stereo",
    observations: `${session}/observations.json`,
    output: packagePath,
    leftMono: "../../artifacts/calibration/cam1",
    rightMono: "../../artifacts/calibration/cam2",
  };
  state.inspectionReportPath = "../../docs/calibration_capture_quality_stereo_YYYYMMDD.md";
  state.detectionReportPath = "../../docs/calibration_charuco_detection_stereo_YYYYMMDD.md";
  updateSessionPaths(session);
  state.verifyPath = packagePath;
}

function applyMonoPreset(options: {
  cameraId: string;
  device: string;
  session: string;
  packagePath: string;
  inspectReport: string;
  detectReport: string;
}): void {
  state.captureOptions = {
    ...state.captureOptions,
    topology: "mono",
    cameraId: options.cameraId,
    device: options.device,
    output: options.session,
  };
  state.solveOptions = {
    ...state.solveOptions,
    topology: "mono",
    observations: `${options.session}/observations.json`,
    output: options.packagePath,
    cameraId: options.cameraId,
  };
  state.inspectionReportPath = options.inspectReport;
  state.detectionReportPath = options.detectReport;
  updateSessionPaths(options.session);
  state.verifyPath = options.packagePath;
}

function updateSessionPaths(session: string): void {
  state.sessionPath = session;
  state.observationsPath = `${session}/observations.json`;
  state.solveOptions.observations = state.observationsPath;
}

async function runCalibrationCommand(id: CommandId): Promise<void> {
  const command = buildCommand(id);
  state.commandRuns[id] = {
    status: "running",
    detail: "Command is running on the local calibration server.",
    stdout: "",
    stderr: "",
  };
  render();

  try {
    const response = await fetch("/api/calibration/run", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ command }),
    });
    const payload = (await response.json()) as {
      status?: CommandRunView["status"];
      exitCode?: number | null;
      durationMs?: number;
      stdout?: string;
      stderr?: string;
      error?: string;
      artifacts?: unknown[];
    };
    const status = payload.status ?? (response.ok ? "passed" : "error");
    const importedArtifactCount = importGeneratedArtifacts(payload.artifacts);
    state.commandRuns[id] = {
      status,
      detail:
        (payload.error ??
          `Exit ${payload.exitCode ?? "unknown"} after ${payload.durationMs ?? "unknown"} ms.`) +
        (importedArtifactCount > 0 ? ` Imported ${importedArtifactCount} artifact(s).` : ""),
      stdout: payload.stdout ?? "",
      stderr: payload.stderr ?? "",
    };
  } catch (error) {
    state.commandRuns[id] = {
      status: "error",
      detail: error instanceof Error ? error.message : String(error),
      stdout: "",
      stderr: "",
    };
  }
  render();
}

function importGeneratedArtifacts(artifacts: unknown[] | undefined): number {
  if (!Array.isArray(artifacts)) return 0;
  let importedCount = 0;
  for (const artifact of artifacts) {
    if (!isJsonObject(artifact) || !isJsonObject(artifact.payload)) continue;
    const name = typeof artifact.name === "string" ? artifact.name : "generated.json";
    const path = typeof artifact.path === "string" ? artifact.path : name;
    const payload = artifact.payload;
    state.artifacts.push({
      id: `${path}:${Date.now()}:${importedCount}`,
      name: path,
      kind: classifyArtifact(payload),
      payload,
    });
    importedCount += 1;
  }
  return importedCount;
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
      id: "sample-target",
      name: "target.json",
      kind: "targetSheet",
      payload: {
        schema_version: "calibration.target_sheet.v1",
        accepted: true,
        dpi: 300,
        target: {
          type: "charuco",
          profile: "dfoptix_charuco_15mm",
          dictionary: "DICT_5X5_100",
          squares_x: 14,
          squares_y: 9,
          square_size_m: 0.015,
        },
        board_size_mm: { width: 210, height: 135 },
      },
    },
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

function isJsonObject(value: unknown): value is JsonObject {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function escapeHtml(value: string): string {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}
