import { existsSync } from "node:fs";
import { join } from "node:path";

const distDir = join(import.meta.dirname, "..", "dist");
const port = Number(process.env.PORT ?? 5178);

function contentType(pathname) {
  if (pathname.endsWith(".html")) return "text/html; charset=utf-8";
  if (pathname.endsWith(".js")) return "text/javascript; charset=utf-8";
  if (pathname.endsWith(".css")) return "text/css; charset=utf-8";
  return "application/octet-stream";
}

Bun.serve({
  port,
  async fetch(request) {
    const url = new URL(request.url);
    const pathname = url.pathname === "/" ? "/index.html" : url.pathname;
    const filePath = join(distDir, pathname);

    if (!filePath.startsWith(distDir) || !existsSync(filePath)) {
      return new Response("Not found", { status: 404 });
    }

    return new Response(Bun.file(filePath), {
      headers: { "content-type": contentType(pathname) },
    });
  },
});

console.log(`Live3D fixture UI available at http://localhost:${port}`);
