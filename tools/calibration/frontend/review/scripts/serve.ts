import { existsSync, realpathSync, statSync } from "node:fs";
import { resolve, sep } from "node:path";

import { runCalibrationCommand } from "./calibration-command-runner";

const appDir = resolve(import.meta.dirname, "..");
const repoRoot = resolve(appDir, "..", "..", "..", "..");
const distDir = resolve(appDir, "dist");
const artifactsDir = resolve(repoRoot, "artifacts");
const port = Number(process.env.PORT ?? 5188);
const host = process.env.HOST ?? "127.0.0.1";

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

if (import.meta.main) {
  startServer();
  await new Promise(() => undefined);
}
