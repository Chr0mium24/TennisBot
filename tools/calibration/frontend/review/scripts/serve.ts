import { existsSync, realpathSync, statSync } from "node:fs";
import { resolve, sep } from "node:path";

const appDir = resolve(import.meta.dirname, "..");
const repoRoot = resolve(appDir, "..", "..", "..", "..");
const distDir = resolve(appDir, "dist");
const artifactsDir = resolve(repoRoot, "artifacts");
const port = Number(process.env.PORT ?? 5188);

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
    async fetch(request) {
      const resolvedPath = resolveStaticRequestPath(new URL(request.url).pathname);
      if (resolvedPath === null) return new Response("Not found", { status: 404 });
      return new Response(Bun.file(resolvedPath.filePath), {
        headers: { "content-type": contentType(resolvedPath.contentPath) },
      });
    },
  });
  console.log(`Calibration review UI available at http://localhost:${port}`);
  return server;
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

if (import.meta.main) {
  startServer();
  await new Promise(() => undefined);
}
