import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "bun:test";

import { contentType, resolveStaticRequestPath } from "./serve";

describe("calibration review server", () => {
  test("serves static dist files and artifact files inside allowed roots", () => {
    const root = makeTempRoot();
    const distDir = join(root, "dist");
    const artifactsDir = join(root, "artifacts");
    mkdirSync(distDir, { recursive: true });
    mkdirSync(join(artifactsDir, "calibration", "cam1"), { recursive: true });
    writeFileSync(join(distDir, "index.html"), "");
    writeFileSync(join(artifactsDir, "calibration", "cam1", "package.json"), "{}");

    expect(resolveStaticRequestPath("/", { distDir, artifactsDir })?.contentPath).toBe("/index.html");
    expect(resolveStaticRequestPath("/artifacts/calibration/cam1/package.json", { distDir, artifactsDir })?.contentPath).toBe(
      "/artifacts/calibration/cam1/package.json",
    );
    expect(resolveStaticRequestPath("/artifacts/../package.json", { distDir, artifactsDir })).toBeNull();
  });

  test("returns stable content types", () => {
    expect(contentType("/index.html")).toContain("text/html");
    expect(contentType("/assets/main.js")).toContain("text/javascript");
    expect(contentType("/styles.css")).toContain("text/css");
    expect(contentType("/artifacts/package.json")).toContain("application/json");
  });
});

function makeTempRoot(): string {
  return join(process.cwd(), ".tmp-test", String(Date.now()), String(Math.random()).slice(2));
}
