import { existsSync, realpathSync, statSync } from "node:fs";
import { resolve, sep } from "node:path";

const distDir = resolve(import.meta.dirname, "..", "dist");
const artifactsDir = resolve(import.meta.dirname, "..", "..", "..", "artifacts");
const port = Number(process.env.PORT ?? 5178);

function contentType(pathname) {
  if (pathname.endsWith(".html")) return "text/html; charset=utf-8";
  if (pathname.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (pathname.endsWith(".css")) return "text/css; charset=utf-8";
  if (pathname.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

export function resolveStaticRequestPath(
  pathname,
  roots = { distDir, artifactsDir },
) {
  const decodedPathname = decodePathname(pathname);
  if (decodedPathname === null) {
    return null;
  }

  if (decodedPathname === "/artifacts" || decodedPathname === "/artifacts/") {
    return null;
  }

  if (decodedPathname.startsWith("/artifacts/")) {
    const relativePath = decodedPathname.slice("/artifacts/".length);
    const filePath = resolve(roots.artifactsDir, relativePath);
    return isServableFileInRoot(filePath, roots.artifactsDir)
      ? { filePath, contentPath: decodedPathname }
      : null;
  }

  const contentPath = decodedPathname === "/" ? "/index.html" : decodedPathname;
  const relativePath = contentPath.replace(/^\/+/, "");
  const filePath = resolve(roots.distDir, relativePath);
  return isServableFileInRoot(filePath, roots.distDir)
    ? { filePath, contentPath }
    : null;
}

export function startServer() {
  Bun.serve({
    port,
    async fetch(request) {
      const url = new URL(request.url);
      const resolvedPath = resolveStaticRequestPath(url.pathname);

      if (resolvedPath === null) {
        return new Response("Not found", { status: 404 });
      }

      return new Response(Bun.file(resolvedPath.filePath), {
        headers: { "content-type": contentType(resolvedPath.contentPath) },
      });
    },
  });

  console.log(`Live3D fixture UI available at http://localhost:${port}`);
}

function decodePathname(pathname) {
  try {
    const decoded = decodeURIComponent(pathname);
    return decoded.includes("\0") ? null : decoded;
  } catch {
    return null;
  }
}

function isInsideRoot(filePath, root) {
  const resolvedRoot = resolve(root);
  return filePath === resolvedRoot || filePath.startsWith(`${resolvedRoot}${sep}`);
}

function isServableFileInRoot(filePath, root) {
  if (!existsSync(root) || !existsSync(filePath)) {
    return false;
  }

  const realRoot = realpathSync(root);
  const realFilePath = realpathSync(filePath);
  return statSync(realFilePath).isFile() && isInsideRoot(realFilePath, realRoot);
}

if (import.meta.main) {
  startServer();
}
