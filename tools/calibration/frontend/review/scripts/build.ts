import { copyFileSync, mkdirSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const appDir = resolve(import.meta.dirname, "..");
const distDir = resolve(appDir, "dist");

rmSync(distDir, { recursive: true, force: true });
mkdirSync(distDir, { recursive: true });

const result = await Bun.build({
  entrypoints: [resolve(appDir, "src", "main.ts")],
  outdir: resolve(distDir, "assets"),
  target: "browser",
});

if (!result.success) {
  for (const log of result.logs) {
    console.error(log);
  }
  process.exit(1);
}

copyFileSync(resolve(appDir, "index.html"), resolve(distDir, "index.html"));
copyFileSync(resolve(appDir, "src", "styles.css"), resolve(distDir, "styles.css"));
