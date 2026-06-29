import { existsSync, readFileSync, realpathSync, statSync } from "node:fs";
import { basename, resolve, sep } from "node:path";

import { runCalibrationCommand } from "./calibration-command-runner";

const appDir = resolve(import.meta.dirname, "..");
const repoRoot = resolve(appDir, "..", "..", "..", "..");
const distDir = resolve(appDir, "dist");
const artifactsDir = resolve(repoRoot, "artifacts");
const port = Number(process.env.PORT ?? 5188);
const host = process.env.HOST ?? "127.0.0.1";
const currentArtifactPaths = [
  "artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
  "artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json",
  "artifacts/calibration_sessions/cam1_session/manifest.json",
  "artifacts/calibration_sessions/cam1_session/inspection.json",
  "artifacts/calibration_sessions/cam1_session/observations.json",
  "artifacts/calibration_sessions/cam2_session/manifest.json",
  "artifacts/calibration_sessions/cam2_session/inspection.json",
  "artifacts/calibration_sessions/cam2_session/observations.json",
  "artifacts/calibration_sessions/stereo_session/manifest.json",
  "artifacts/calibration_sessions/stereo_session/inspection.json",
  "artifacts/calibration_sessions/stereo_session/observations.json",
  "artifacts/calibration/cam1/package.json",
  "artifacts/calibration/cam1/verification.json",
  "artifacts/calibration/cam2/package.json",
  "artifacts/calibration/cam2/verification.json",
  "artifacts/calibration/stereo_cam1_cam2/package.json",
  "artifacts/calibration/stereo_cam1_cam2/verification.json",
] as const;

type CurrentCalibrationArtifact = {
  name: string;
  path: string;
  payload: Record<string, unknown>;
};

export type CameraDeviceEntry = {
  label: string;
  paths: string[];
};

type ExpectedCameraDevice = {
  role: "cam1" | "cam2";
  path: string;
  present: boolean;
};

type CameraDeviceStatusPayload = {
  schema_version: "tennisbot.camera_devices_status.v1";
  result: "passed" | "failed";
  command: string[];
  exit_code: number;
  expected: ExpectedCameraDevice[];
  devices: CameraDeviceEntry[];
  stdout: string;
  stderr: string;
};

export function contentType(pathname: string): string {
  if (pathname.endsWith(".html")) return "text/html; charset=utf-8";
  if (pathname.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (pathname.endsWith(".css")) return "text/css; charset=utf-8";
  if (pathname.endsWith(".json")) return "application/json; charset=utf-8";
  if (pathname.endsWith(".png")) return "image/png";
  if (pathname.endsWith(".jpg") || pathname.endsWith(".jpeg")) return "image/jpeg";
  return "application/octet-stream";
}

export function resolveStaticRequestPath(
  pathname: string,
  roots = { distDir, artifactsDir },
): { filePath: string; contentPath: string } | null {
  const decodedPathname = decodePathname(pathname);
  if (decodedPathname === null) return null;
  if (decodedPathname.startsWith("/artifacts/")) {
    const filePath = resolve(roots.artifactsDir, decodedPathname.slice("/artifacts/".length));
    return isServableFileInRoot(filePath, roots.artifactsDir) ? { filePath, contentPath: decodedPathname } : null;
  }
  const contentPath = decodedPathname === "/" ? "/index.html" : decodedPathname;
  const filePath = resolve(roots.distDir, contentPath.replace(/^\/+/, ""));
  return isServableFileInRoot(filePath, roots.distDir) ? { filePath, contentPath } : null;
}

export function startServer() {
  const server = Bun.serve({
    port,
    hostname: host,
    async fetch(request) {
      const url = new URL(request.url);
      if (url.pathname === "/api/calibration/run") {
        return handleCalibrationRunRequest(request);
      }
      if (url.pathname === "/api/physical/status") {
        return handlePhysicalStatusRequest(request);
      }
      if (url.pathname === "/api/calibration/current-artifacts") {
        return handleCurrentArtifactsRequest(request);
      }
      if (url.pathname === "/api/camera-devices/status") {
        return handleCameraDevicesStatusRequest(request);
      }
      const resolvedPath = resolveStaticRequestPath(url.pathname);
      if (resolvedPath === null) return new Response("Not found", { status: 404 });
      return new Response(Bun.file(resolvedPath.filePath), {
        headers: { "content-type": contentType(resolvedPath.contentPath) },
      });
    },
  });
  console.log(`Calibration review UI available at http://${host}:${port}`);
  return server;
}

export async function handleCalibrationRunRequest(request: Request): Promise<Response> {
  if (request.method !== "POST") {
    return jsonResponse({ error: "Use POST." }, 405);
  }
  let payload: unknown;
  try {
    payload = await request.json();
  } catch {
    return jsonResponse({ error: "Request body must be JSON." }, 400);
  }
  const command = typeof payload === "object" && payload !== null ? (payload as { command?: unknown }).command : undefined;
  if (typeof command !== "string" || command.trim() === "") {
    return jsonResponse({ error: "Request JSON must contain a non-empty command string." }, 400);
  }
  const result = await runCalibrationCommand(command);
  return jsonResponse(result, result.status === "rejected" ? 400 : 200);
}

export async function handlePhysicalStatusRequest(request: Request): Promise<Response> {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Use GET." }, 405);
  }
  const timestamp = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const reportPath = `/tmp/tennisbot_physical_status_${timestamp}.md`;
  const jsonPath = `/tmp/tennisbot_physical_status_${timestamp}.json`;
  const childProcess = Bun.spawn(
    [
      "bun",
      "scripts/physical-validation-status.ts",
      "--output",
      reportPath,
      "--output-json",
      jsonPath,
    ],
    {
      cwd: repoRoot,
      env: processEnv(),
      stdin: "ignore",
      stdout: "pipe",
      stderr: "pipe",
    },
  );
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(childProcess.stdout).text(),
    new Response(childProcess.stderr).text(),
    childProcess.exited,
  ]);
  try {
    const payload = await Bun.file(jsonPath).json();
    return jsonResponse({ ...payload, report_path: reportPath, exit_code: exitCode });
  } catch (error) {
    return jsonResponse(
      {
        error: error instanceof Error ? error.message : String(error),
        exit_code: exitCode,
        stdout,
        stderr,
      },
      500,
    );
  }
}

export async function handleCurrentArtifactsRequest(request: Request): Promise<Response> {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Use GET." }, 405);
  }
  return jsonResponse({
    schema_version: "tennisbot.calibration_current_artifacts.v1",
    artifacts: collectCurrentCalibrationArtifacts(),
  });
}

export function collectCurrentCalibrationArtifacts(root = repoRoot): CurrentCalibrationArtifact[] {
  const artifacts: CurrentCalibrationArtifact[] = [];
  for (const relativePath of currentArtifactPaths) {
    const path = resolve(root, relativePath);
    if (!isServableFileInRoot(path, resolve(root, "artifacts"))) continue;
    const payload = parseJsonObject(readFileSync(path, "utf-8"));
    if (payload === undefined) continue;
    artifacts.push({
      name: basename(path),
      path: relativePath,
      payload,
    });
  }
  return artifacts;
}

export async function handleCameraDevicesStatusRequest(request: Request): Promise<Response> {
  if (request.method !== "GET") {
    return jsonResponse({ error: "Use GET." }, 405);
  }
  return jsonResponse(await cameraDevicesStatus());
}

async function cameraDevicesStatus(): Promise<CameraDeviceStatusPayload> {
  const command = ["v4l2-ctl", "--list-devices"];
  let childProcess: ReturnType<typeof Bun.spawn>;
  try {
    childProcess = Bun.spawn(command, {
      cwd: repoRoot,
      env: processEnv(),
      stdin: "ignore",
      stdout: "pipe",
      stderr: "pipe",
    });
  } catch (error) {
    return {
      schema_version: "tennisbot.camera_devices_status.v1",
      result: "failed",
      command,
      exit_code: -1,
      expected: expectedCameraDevices([]),
      devices: [],
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
    };
  }
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(childProcess.stdout).text(),
    new Response(childProcess.stderr).text(),
    childProcess.exited,
  ]);
  const devices = parseV4l2DeviceList(stdout);
  const expected = expectedCameraDevices(devices);
  return {
    schema_version: "tennisbot.camera_devices_status.v1",
    result: exitCode === 0 && expected.every((device) => device.present) ? "passed" : "failed",
    command,
    exit_code: exitCode,
    expected,
    devices,
    stdout,
    stderr,
  };
}

export function parseV4l2DeviceList(output: string): CameraDeviceEntry[] {
  const devices: CameraDeviceEntry[] = [];
  let current: CameraDeviceEntry | undefined;
  for (const line of output.split("\n")) {
    if (line.trim() === "") continue;
    const videoPaths = [...line.matchAll(/\/dev\/video\d+/gu)].map((match) => match[0]);
    if (line.startsWith("\t") || line.startsWith(" ")) {
      if (videoPaths.length === 0) continue;
      if (current === undefined) {
        current = { label: "Unlabeled camera", paths: [] };
        devices.push(current);
      }
      current.paths.push(...videoPaths);
      continue;
    }
    current = { label: line.trim().replace(/:$/u, ""), paths: videoPaths };
    devices.push(current);
  }
  return devices.filter((device) => device.paths.length > 0);
}

function expectedCameraDevices(devices: CameraDeviceEntry[]): ExpectedCameraDevice[] {
  const paths = new Set(devices.flatMap((device) => device.paths));
  return [
    { role: "cam1", path: "/dev/video0", present: paths.has("/dev/video0") },
    { role: "cam2", path: "/dev/video2", present: paths.has("/dev/video2") },
  ];
}

function decodePathname(pathname: string): string | null {
  try {
    const decoded = decodeURIComponent(pathname);
    return decoded.includes("\0") ? null : decoded;
  } catch {
    return null;
  }
}

function isInsideRoot(filePath: string, root: string): boolean {
  const resolvedRoot = resolve(root);
  return filePath === resolvedRoot || filePath.startsWith(`${resolvedRoot}${sep}`);
}

function isServableFileInRoot(filePath: string, root: string): boolean {
  if (!existsSync(root) || !existsSync(filePath)) return false;
  const realRoot = realpathSync(root);
  const realFilePath = realpathSync(filePath);
  return statSync(realFilePath).isFile() && isInsideRoot(realFilePath, realRoot);
}

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload, null, 2), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function processEnv(): Record<string, string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
}

function parseJsonObject(text: string): Record<string, unknown> | undefined {
  try {
    const value = JSON.parse(text) as unknown;
    return value !== null && typeof value === "object" && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : undefined;
  } catch {
    return undefined;
  }
}

if (import.meta.main) {
  startServer();
  await new Promise(() => undefined);
}
