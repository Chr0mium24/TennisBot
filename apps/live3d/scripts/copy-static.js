import { copyFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const distDir = join(import.meta.dirname, "..", "dist");
mkdirSync(distDir, { recursive: true });
copyFileSync(join(import.meta.dirname, "..", "index.html"), join(distDir, "index.html"));
