import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";

const distDir = join(import.meta.dirname, "..", "dist");
const assetsDir = join(distDir, "assets");
mkdirSync(distDir, { recursive: true });
mkdirSync(assetsDir, { recursive: true });
copyFileSync(join(import.meta.dirname, "..", "index.html"), join(distDir, "index.html"));

const ortDistDir = join(import.meta.dirname, "..", "node_modules", "onnxruntime-web", "dist");
for (const filename of readdirSync(ortDistDir)) {
  const isOrtWasmSidecar =
    filename.startsWith("ort-wasm-simd-threaded.") &&
    (filename.endsWith(".wasm") || filename.endsWith(".mjs"));
  if (isOrtWasmSidecar) {
    copyFileSync(join(ortDistDir, filename), join(assetsDir, filename));
  }
}
