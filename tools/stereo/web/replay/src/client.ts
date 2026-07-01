import * as THREE from "three";

type SessionSummary = {
  id: string;
  createdAt: string | null;
  pointCount: number;
  startSec: number | null;
  endSec: number | null;
  durationSec: number | null;
};

type RecordedPoint = {
  frameId: number;
  elapsedSec: number;
  position: { x: number; y: number; z: number };
  confidence?: number;
  disparityPx?: number;
  epipolarErrorPx?: number;
  reprojectionErrorPx?: number;
};

type SessionDetail = {
  summary: SessionSummary;
  metadata: unknown;
  points: RecordedPoint[];
};

type Prediction = {
  model: "linear" | "quadratic";
  samples: RecordedPoint[];
};

const sessionList = requireElement<HTMLDivElement>("session-list");
const recordTitle = requireElement<HTMLHeadingElement>("record-title");
const recordStats = requireElement<HTMLDivElement>("record-stats");
const startRange = requireElement<HTMLInputElement>("start-range");
const endRange = requireElement<HTMLInputElement>("end-range");
const startLabel = requireElement<HTMLOutputElement>("start-label");
const endLabel = requireElement<HTMLOutputElement>("end-label");
const selectionStats = requireElement<HTMLParagraphElement>("selection-stats");
const predictionStats = requireElement<HTMLParagraphElement>("prediction-stats");
const emptyState = requireElement<HTMLDivElement>("empty-state");
const canvas = requireElement<HTMLCanvasElement>("scene");

let sessions: SessionSummary[] = [];
let active: SessionDetail | null = null;
let selectedSessionId: string | null = null;

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setClearColor(0x101414);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(55, 1, 0.01, 200);
camera.position.set(0, 2.2, 7);
camera.lookAt(0, 0, 0);

const group = new THREE.Group();
scene.add(group);
scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const light = new THREE.DirectionalLight(0xffffff, 1.4);
light.position.set(4, 6, 3);
scene.add(light);

const grid = new THREE.GridHelper(8, 16, 0x52615a, 0x2b3632);
grid.position.y = -1.2;
scene.add(grid);

let allPointsObject: THREE.Points | null = null;
let selectedPointsObject: THREE.Points | null = null;
let selectedLineObject: THREE.Line | null = null;
let predictionLineObject: THREE.Line | null = null;
let rotationX = -0.25;
let rotationY = 0.45;
let dragging = false;
let lastMouse: { x: number; y: number } | null = null;

canvas.addEventListener("pointerdown", (event) => {
  dragging = true;
  lastMouse = { x: event.clientX, y: event.clientY };
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointerup", (event) => {
  dragging = false;
  lastMouse = null;
  canvas.releasePointerCapture(event.pointerId);
});

canvas.addEventListener("pointermove", (event) => {
  if (!dragging || lastMouse === null) return;
  rotationY += (event.clientX - lastMouse.x) * 0.006;
  rotationX += (event.clientY - lastMouse.y) * 0.006;
  rotationX = clamp(rotationX, -1.2, 1.2);
  lastMouse = { x: event.clientX, y: event.clientY };
  updateGroupRotation();
});

startRange.addEventListener("input", updateSelectionFromRanges);
endRange.addEventListener("input", updateSelectionFromRanges);
window.addEventListener("resize", resizeRenderer);

void init();
animate();

async function init(): Promise<void> {
  sessions = await fetchJson<SessionSummary[]>("/api/sessions");
  renderSessionList();
  resizeRenderer();
  if (sessions.length > 0) {
    await selectSession(sessions[0]!.id);
  }
}

function renderSessionList(): void {
  if (sessions.length === 0) {
    sessionList.innerHTML = `<div class="session-button"><strong>No records</strong><span>No recorded sessions found.</span></div>`;
    return;
  }
  sessionList.innerHTML = sessions
    .map((session) => {
      const activeClass = session.id === selectedSessionId ? " active" : "";
      return `
        <button class="session-button${activeClass}" type="button" data-session="${escapeHtml(session.id)}">
          <strong>${escapeHtml(session.id)}</strong>
          <span>${session.pointCount} point(s), ${formatDuration(session.durationSec)}</span>
        </button>
      `;
    })
    .join("");
  for (const button of sessionList.querySelectorAll<HTMLButtonElement>("[data-session]")) {
    button.addEventListener("click", () => {
      const id = button.dataset.session;
      if (id !== undefined) void selectSession(id);
    });
  }
}

async function selectSession(id: string): Promise<void> {
  selectedSessionId = id;
  active = await fetchJson<SessionDetail>(`/api/sessions/${encodeURIComponent(id)}`);
  renderSessionList();
  recordTitle.textContent = active.summary.id;
  recordStats.textContent = `${active.summary.pointCount} point(s) | ${formatDuration(active.summary.durationSec)}`;
  configureRanges(active.points);
  drawAllPoints(active.points);
  updateSelectionFromRanges();
}

function configureRanges(points: RecordedPoint[]): void {
  const minMs = Math.round((points[0]?.elapsedSec ?? 0) * 1000);
  const maxMs = Math.round((points.at(-1)?.elapsedSec ?? 0) * 1000);
  for (const input of [startRange, endRange]) {
    input.min = String(minMs);
    input.max = String(Math.max(minMs, maxMs));
    input.step = "10";
  }
  startRange.value = String(minMs);
  endRange.value = String(Math.max(minMs, maxMs));
}

function updateSelectionFromRanges(): void {
  if (active === null) return;
  let startMs = Number(startRange.value);
  let endMs = Number(endRange.value);
  if (startMs > endMs) {
    if (document.activeElement === startRange) {
      endMs = startMs;
      endRange.value = String(endMs);
    } else {
      startMs = endMs;
      startRange.value = String(startMs);
    }
  }

  startLabel.value = formatSeconds(startMs / 1000);
  endLabel.value = formatSeconds(endMs / 1000);
  const selected = active.points.filter((point) => point.elapsedSec * 1000 >= startMs && point.elapsedSec * 1000 <= endMs);
  const prediction = predictSelectedPoints(selected);
  drawSelectedPoints(selected, prediction);
  renderSelectionStats(selected, prediction);
}

function renderSelectionStats(selected: RecordedPoint[], prediction: Prediction | null): void {
  emptyState.classList.toggle("hidden", selected.length > 0);
  if (selected.length === 0) {
    selectionStats.textContent = "No points in the selected time range.";
    predictionStats.textContent = "Prediction waits for selected points.";
    return;
  }
  const first = selected[0]!;
  const last = selected.at(-1)!;
  selectionStats.textContent = `${selected.length} point(s), ${formatSeconds(first.elapsedSec)} to ${formatSeconds(last.elapsedSec)}. Latest point: x=${last.position.x.toFixed(3)} y=${last.position.y.toFixed(3)} z=${last.position.z.toFixed(3)} m.`;
  predictionStats.textContent =
    prediction === null
      ? "Prediction waits for at least two selected points."
      : `${prediction.model} camera-frame fit, ${prediction.samples.length} future sample(s), horizon ${(prediction.samples.at(-1)?.elapsedSec ?? 0).toFixed(2)}s from selected start.`;
}

function drawAllPoints(points: RecordedPoint[]): void {
  if (allPointsObject !== null) group.remove(allPointsObject);
  allPointsObject = makePoints(points, 0x8b9690, 0.028);
  group.add(allPointsObject);
}

function drawSelectedPoints(selected: RecordedPoint[], prediction: Prediction | null): void {
  for (const object of [selectedPointsObject, selectedLineObject, predictionLineObject]) {
    if (object !== null) group.remove(object);
  }
  selectedPointsObject = makePoints(selected, 0x78f08a, 0.055);
  selectedLineObject = makeLine(selected, 0x78f08a);
  predictionLineObject = prediction === null ? null : makeLine(prediction.samples, 0xf4d03f);
  group.add(selectedPointsObject);
  if (selectedLineObject !== null) group.add(selectedLineObject);
  if (predictionLineObject !== null) group.add(predictionLineObject);
}

function makePoints(points: RecordedPoint[], color: number, size: number): THREE.Points {
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flatMap((point) => vectorFor(point)), 3));
  const material = new THREE.PointsMaterial({ color, size, sizeAttenuation: true });
  return new THREE.Points(geometry, material);
}

function makeLine(points: RecordedPoint[], color: number): THREE.Line | null {
  if (points.length < 2) return null;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points.flatMap((point) => vectorFor(point)), 3));
  const material = new THREE.LineBasicMaterial({ color, linewidth: 2 });
  return new THREE.Line(geometry, material);
}

function vectorFor(point: RecordedPoint): [number, number, number] {
  return [point.position.x, -point.position.y, -point.position.z];
}

function predictSelectedPoints(points: RecordedPoint[]): Prediction | null {
  if (points.length < 2) return null;
  const firstSec = points[0]!.elapsedSec;
  const times = points.map((point) => point.elapsedSec - firstSec);
  const model = points.length >= 3 ? "quadratic" : "linear";
  const fitX = fitAxis(times, points.map((point) => point.position.x), model);
  const fitY = fitAxis(times, points.map((point) => point.position.y), model);
  const fitZ = fitAxis(times, points.map((point) => point.position.z), model);
  const lastT = times.at(-1)!;
  const horizon = 1.0;
  const samples = Array.from({ length: 24 }, (_, index) => {
    const t = lastT + (horizon * index) / 23;
    return {
      frameId: points.at(-1)!.frameId + index,
      elapsedSec: t,
      position: {
        x: evaluateFit(fitX, t),
        y: evaluateFit(fitY, t),
        z: evaluateFit(fitZ, t),
      },
    };
  });
  return { model, samples };
}

function fitAxis(times: number[], values: number[], model: "linear" | "quadratic"): [number, number, number] {
  if (model === "linear") {
    const n = times.length;
    const sumT = sum(times);
    const sumV = sum(values);
    const sumTT = sum(times.map((t) => t * t));
    const sumTV = sum(times.map((t, index) => t * values[index]!));
    const denominator = n * sumTT - sumT * sumT;
    const b = Math.abs(denominator) < 1e-9 ? 0 : (n * sumTV - sumT * sumV) / denominator;
    const c = (sumV - b * sumT) / n;
    return [0, b, c];
  }

  const rows: [number, number, number][] = [];
  const rhs: [number, number, number] = [0, 0, 0];
  const basis = times.map((t) => [t * t, t, 1] as [number, number, number]);
  for (let row = 0; row < 3; row += 1) {
    rows[row] = [0, 0, 0];
    for (let col = 0; col < 3; col += 1) {
      rows[row]![col] = sum(basis.map((b) => b[row] * b[col]));
    }
    rhs[row] = sum(basis.map((b, index) => b[row] * values[index]!));
  }
  return solve3x3(rows as [[number, number, number], [number, number, number], [number, number, number]], rhs);
}

function evaluateFit(coefficients: [number, number, number], t: number): number {
  return coefficients[0] * t * t + coefficients[1] * t + coefficients[2];
}

function solve3x3(
  matrix: [[number, number, number], [number, number, number], [number, number, number]],
  vector: [number, number, number],
): [number, number, number] {
  const augmented = matrix.map((row, index) => [...row, vector[index]]) as [
    [number, number, number, number],
    [number, number, number, number],
    [number, number, number, number],
  ];
  for (let pivot = 0; pivot < 3; pivot += 1) {
    let best = pivot;
    for (let row = pivot + 1; row < 3; row += 1) {
      if (Math.abs(augmented[row][pivot]) > Math.abs(augmented[best][pivot])) best = row;
    }
    if (Math.abs(augmented[best][pivot]) < 1e-9) return [0, 0, vector[2] ?? 0];
    [augmented[pivot], augmented[best]] = [augmented[best], augmented[pivot]];
    const scale = augmented[pivot][pivot];
    for (let col = pivot; col < 4; col += 1) augmented[pivot][col] /= scale;
    for (let row = 0; row < 3; row += 1) {
      if (row === pivot) continue;
      const factor = augmented[row][pivot];
      for (let col = pivot; col < 4; col += 1) augmented[row][col] -= factor * augmented[pivot][col];
    }
  }
  return [augmented[0][3], augmented[1][3], augmented[2][3]];
}

function updateGroupRotation(): void {
  group.rotation.x = rotationX;
  group.rotation.y = rotationY;
}

function resizeRenderer(): void {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.floor(rect.width));
  const height = Math.max(1, Math.floor(rect.height));
  renderer.setSize(width, height, false);
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
}

function animate(): void {
  updateGroupRotation();
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

function requireElement<T extends HTMLElement>(id: string): T {
  const element = document.getElementById(id);
  if (element === null) throw new Error(`missing #${id}`);
  return element as T;
}

function sum(values: number[]): number {
  return values.reduce((total, value) => total + value, 0);
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function formatDuration(value: number | null): string {
  return value === null ? "0.00s" : `${value.toFixed(2)}s`;
}

function formatSeconds(value: number): string {
  return `${value.toFixed(2)}s`;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
