import { describe, expect, test } from "bun:test";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { contentType, resolveStaticRequestPath } from "./serve.js";

describe("Live3D dev server path mapping", () => {
  test("serves /artifacts only from the repo-root artifacts directory", () => {
    const root = mkdtempSync(join(tmpdir(), "live3d-serve-"));
    const distDir = join(root, "dist");
    const artifactsDir = join(root, "artifacts");
    const outsideDir = join(root, "outside");

    try {
      mkdirSync(join(artifactsDir, "models", "tennis_ball_yolo"), { recursive: true });
      mkdirSync(distDir, { recursive: true });
      mkdirSync(outsideDir, { recursive: true });
      writeFileSync(join(artifactsDir, "models", "tennis_ball_yolo", "package.json"), "{}");
      writeFileSync(join(outsideDir, "secret.json"), "{}");
      symlinkSync(
        join(outsideDir, "secret.json"),
        join(artifactsDir, "models", "tennis_ball_yolo", "secret-link.json"),
      );

      const resolved = resolveStaticRequestPath(
        "/artifacts/models/tennis_ball_yolo/package.json",
        { distDir, artifactsDir },
      );
      expect(resolved?.filePath).toBe(
        resolve(artifactsDir, "models", "tennis_ball_yolo", "package.json"),
      );

      expect(
        resolveStaticRequestPath("/artifacts/../outside/secret.json", {
          distDir,
          artifactsDir,
        }),
      ).toBeNull();
      expect(
        resolveStaticRequestPath("/artifacts/%2e%2e/outside/secret.json", {
          distDir,
          artifactsDir,
        }),
      ).toBeNull();
      expect(
        resolveStaticRequestPath("/models/tennis_ball_yolo/package.json", {
          distDir,
          artifactsDir,
        }),
      ).toBeNull();
      expect(
        resolveStaticRequestPath("/artifacts/models/tennis_ball_yolo/secret-link.json", {
          distDir,
          artifactsDir,
        }),
      ).toBeNull();
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });

  test("serves ONNX Runtime Web sidecars with browser-compatible MIME types", () => {
    expect(contentType("/assets/ort-wasm-simd-threaded.mjs")).toBe(
      "text/javascript; charset=utf-8",
    );
    expect(contentType("/assets/ort-wasm-simd-threaded.wasm")).toBe("application/wasm");
  });
});
