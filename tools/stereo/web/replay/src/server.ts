import { readdir, stat } from "node:fs/promises";
import { basename, resolve, sep } from "node:path";

export type ReplayServerOptions = {
  host: string;
  port: number;
  runsRoot: string;
};

export type SessionSummary = {
  id: string;
  path: string;
  createdAt: string | null;
  pointCount: number;
  startSec: number | null;
  endSec: number | null;
  durationSec: number | null;
};

export type RecordedPoint = {
  frameId: number;
  elapsedSec: number;
  timestampUnixMs?: number;
  position: { x: number; y: number; z: number };
  confidence?: number;
  disparityPx?: number;
  epipolarErrorPx?: number;
  reprojectionErrorPx?: number;
};

export type SessionDetail = {
  summary: SessionSummary;
  metadata: unknown;
  points: RecordedPoint[];
};

const repoRoot = resolve(import.meta.dirname, "../../../../..");
const replayRoot = resolve(import.meta.dirname, "..");
const publicRoot = resolve(replayRoot, "public");
const distRoot = resolve(replayRoot, "dist");

if (import.meta.main) {
  const options = parseArgs(Bun.argv.slice(2));
  if (options === null) {
    printUsage();
    process.exit(0);
  }
  const server = startReplayServer(options);
  console.log(`Stereo replay: http://${server.hostname}:${server.port}/`);
  console.log(`runs_root=${options.runsRoot}`);
}

export function startReplayServer(options: ReplayServerOptions): ReturnType<typeof Bun.serve> {
  const runsRoot = resolve(options.runsRoot);
  return Bun.serve({
    hostname: options.host,
    port: options.port,
    async fetch(request) {
      const url = new URL(request.url);
      try {
        if (url.pathname === "/api/sessions") {
          return json(await listSessions(runsRoot));
        }
        const match = url.pathname.match(/^\/api\/sessions\/([^/]+)$/);
        if (match) {
          return json(await loadSession(runsRoot, decodeURIComponent(match[1])));
        }
        return await serveStatic(url.pathname);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        return json({ error: message }, 500);
      }
    },
  });
}

export async function listSessions(runsRoot: string): Promise<SessionSummary[]> {
  const root = resolve(runsRoot);
  if (!(await exists(root))) {
    return [];
  }
  const entries = await readdir(root, { withFileTypes: true });
  const summaries = await Promise.all(
    entries
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => summarizeSession(root, entry.name)),
  );
  return summaries
    .filter((summary): summary is SessionSummary => summary !== null)
    .sort((left, right) => (right.createdAt ?? right.id).localeCompare(left.createdAt ?? left.id));
}

export async function loadSession(runsRoot: string, sessionId: string): Promise<SessionDetail> {
  const root = resolve(runsRoot);
  const sessionDir = safeSessionDir(root, sessionId);
  const metadata = await readJson(resolve(sessionDir, "session.json"));
  const points = await readPoints(resolve(sessionDir, "points.ndjson"));
  return {
    summary: summaryFromPoints(sessionId, sessionDir, metadata, points),
    metadata,
    points,
  };
}

async function summarizeSession(root: string, sessionId: string): Promise<SessionSummary | null> {
  const sessionDir = safeSessionDir(root, sessionId);
  if (!(await exists(resolve(sessionDir, "session.json"))) || !(await exists(resolve(sessionDir, "points.ndjson")))) {
    return null;
  }
  const metadata = await readJson(resolve(sessionDir, "session.json"));
  const points = await readPoints(resolve(sessionDir, "points.ndjson"));
  return summaryFromPoints(sessionId, sessionDir, metadata, points);
}

function summaryFromPoints(
  sessionId: string,
  sessionDir: string,
  metadata: unknown,
  points: RecordedPoint[],
): SessionSummary {
  const createdAt = metadata && typeof metadata === "object" && "created_at" in metadata
    ? String((metadata as { created_at?: unknown }).created_at ?? "")
    : null;
  const startSec = points[0]?.elapsedSec ?? null;
  const endSec = points.at(-1)?.elapsedSec ?? null;
  return {
    id: sessionId,
    path: sessionDir,
    createdAt: createdAt === "" ? null : createdAt,
    pointCount: points.length,
    startSec,
    endSec,
    durationSec: startSec === null || endSec === null ? null : Math.max(0, endSec - startSec),
  };
}

async function readPoints(path: string): Promise<RecordedPoint[]> {
  if (!(await exists(path))) {
    return [];
  }
  const text = await Bun.file(path).text();
  const points: RecordedPoint[] = [];
  for (const line of text.split(/\r?\n/)) {
    if (line.trim().length === 0) continue;
    const raw = JSON.parse(line) as {
      frame_id?: number;
      elapsed_sec?: number;
      timestamp_unix_ms?: number;
      position_m?: { x?: number; y?: number; z?: number };
      confidence?: number;
      disparity_px?: number;
      epipolar_error_px?: number;
      reprojection_error_px?: number;
    };
    if (
      typeof raw.frame_id !== "number" ||
      typeof raw.elapsed_sec !== "number" ||
      raw.position_m === undefined ||
      typeof raw.position_m.x !== "number" ||
      typeof raw.position_m.y !== "number" ||
      typeof raw.position_m.z !== "number"
    ) {
      continue;
    }
    points.push({
      frameId: raw.frame_id,
      elapsedSec: raw.elapsed_sec,
      timestampUnixMs: raw.timestamp_unix_ms,
      position: {
        x: raw.position_m.x,
        y: raw.position_m.y,
        z: raw.position_m.z,
      },
      confidence: raw.confidence,
      disparityPx: raw.disparity_px,
      epipolarErrorPx: raw.epipolar_error_px,
      reprojectionErrorPx: raw.reprojection_error_px,
    });
  }
  return points.sort((left, right) => left.elapsedSec - right.elapsedSec);
}

async function readJson(path: string): Promise<unknown> {
  return JSON.parse(await Bun.file(path).text());
}

function safeSessionDir(root: string, sessionId: string): string {
  if (sessionId !== basename(sessionId)) {
    throw new Error("invalid session id");
  }
  const sessionDir = resolve(root, sessionId);
  if (!isInside(sessionDir, root)) {
    throw new Error("invalid session path");
  }
  return sessionDir;
}

async function serveStatic(pathname: string): Promise<Response> {
  const normalized = pathname === "/" ? "/index.html" : pathname;
  const staticRoot = normalized === "/assets/client.js" ? distRoot : publicRoot;
  const filePath = normalized === "/assets/client.js"
    ? resolve(distRoot, "client.js")
    : resolve(publicRoot, normalized.slice(1));
  if (!isInside(filePath, staticRoot)) {
    return new Response("not found", { status: 404 });
  }
  if (!(await exists(filePath))) {
    return new Response("not found", { status: 404 });
  }
  return new Response(Bun.file(filePath), {
    headers: { "content-type": contentType(filePath) },
  });
}

function json(value: unknown, status = 200): Response {
  return new Response(JSON.stringify(value), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function isInside(path: string, root: string): boolean {
  return path === root || path.startsWith(`${root}${sep}`);
}

async function exists(path: string): Promise<boolean> {
  try {
    await stat(path);
    return true;
  } catch {
    return false;
  }
}

function contentType(path: string): string {
  if (path.endsWith(".html")) return "text/html; charset=utf-8";
  if (path.endsWith(".css")) return "text/css; charset=utf-8";
  if (path.endsWith(".js")) return "text/javascript; charset=utf-8";
  return "application/octet-stream";
}

function parseArgs(args: string[]): ReplayServerOptions | null {
  if (args.includes("--help") || args.includes("-h")) return null;
  const options: ReplayServerOptions = {
    host: "127.0.0.1",
    port: 5180,
    runsRoot: resolve(repoRoot, "runs/stereo"),
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--host") {
      options.host = requireValue(args, ++index, arg);
    } else if (arg === "--port") {
      options.port = Number(requireValue(args, ++index, arg));
    } else if (arg === "--runs-root") {
      options.runsRoot = resolve(repoRoot, requireValue(args, ++index, arg));
    } else {
      throw new Error(`unknown replay option: ${arg}`);
    }
  }
  return options;
}

function requireValue(args: string[], index: number, flag: string): string {
  const value = args[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

function printUsage(): void {
  console.log(`用法: bun src/server.ts [--host 127.0.0.1] [--port 5180] [--runs-root runs/stereo]

启动 stereo 记录回放前端。时间段选择在浏览器 UI 中完成，不使用 --from/--to。`);
}
