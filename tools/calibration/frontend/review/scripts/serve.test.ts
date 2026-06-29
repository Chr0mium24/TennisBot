import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, test } from "bun:test";

import {
  collectCurrentCalibrationArtifacts,
  contentType,
  handleCalibrationRunRequest,
  handleCameraDevicesStatusRequest,
  handleCurrentArtifactsRequest,
  handlePhysicalStatusRequest,
  parseV4l2DeviceList,
  resolveStaticRequestPath,
} from "./serve";

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
    expect(contentType("/artifacts/calibration_sessions/session/frames/cam1_0001.png")).toBe("image/png");
    expect(contentType("/artifacts/calibration_sessions/session/frames/cam1_0001.jpg")).toBe("image/jpeg");
  });

  test("rejects non-whitelisted command execution requests", async () => {
    const response = await handleCalibrationRunRequest(
      new Request("http://localhost/api/calibration/run", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ command: "rm -rf ../../artifacts" }),
      }),
    );
    const payload = await response.json();

    expect(response.status).toBe(400);
    expect(payload.status).toBe("rejected");
    expect(payload.error).toContain("Only 'uv run tennisbot-calibration");
  });

  test("physical status endpoint is read-only", async () => {
    const response = await handlePhysicalStatusRequest(
      new Request("http://localhost/api/physical/status", {
        method: "POST",
      }),
    );
    const payload = await response.json();

    expect(response.status).toBe(405);
    expect(payload.error).toBe("Use GET.");
  });

  test("physical status endpoint returns current status JSON", async () => {
    const response = await handlePhysicalStatusRequest(new Request("http://localhost/api/physical/status"));
    const payload = await response.json();

    expect(response.status).toBe(200);
    expect(payload.schema_version).toBe("tennisbot.physical_validation_status.v1");
    expect(["passed", "incomplete"]).toContain(payload.result);
    expect(payload.gates.length).toBeGreaterThan(0);
  });

  test("current artifacts endpoint is read-only", async () => {
    const response = await handleCurrentArtifactsRequest(
      new Request("http://localhost/api/calibration/current-artifacts", {
        method: "POST",
      }),
    );
    const payload = await response.json();

    expect(response.status).toBe(405);
    expect(payload.error).toBe("Use GET.");
  });

  test("camera devices status endpoint is read-only", async () => {
    const response = await handleCameraDevicesStatusRequest(
      new Request("http://localhost/api/camera-devices/status", {
        method: "POST",
      }),
    );
    const payload = await response.json();

    expect(response.status).toBe(405);
    expect(payload.error).toBe("Use GET.");
  });

  test("parses v4l2 camera device groups", () => {
    expect(
      parseV4l2DeviceList(`USB Camera: USB Camera (usb-0000:00:14.0-8):
\t/dev/video0
\t/dev/video1
\t/dev/media0

USB 2.0 Camera: USB Camera (usb-0000:00:14.0-9):
    /dev/video2
    /dev/video3
`),
    ).toEqual([
      {
        label: "USB Camera: USB Camera (usb-0000:00:14.0-8)",
        paths: ["/dev/video0", "/dev/video1"],
      },
      {
        label: "USB 2.0 Camera: USB Camera (usb-0000:00:14.0-9)",
        paths: ["/dev/video2", "/dev/video3"],
      },
    ]);
  });

  test("collects canonical current calibration artifacts", () => {
    const root = makeTempRoot();
    try {
      mkdirSync(join(root, "artifacts", "calibration_targets"), { recursive: true });
      mkdirSync(join(root, "artifacts", "calibration_sessions", "cam1_session"), { recursive: true });
      mkdirSync(join(root, "artifacts", "calibration", "cam1"), { recursive: true });
      writeFileSync(
        join(root, "artifacts", "calibration_targets", "dfoptix_charuco_15mm_300dpi.json"),
        JSON.stringify({ schema_version: "calibration.target_sheet.v1", accepted: true }),
      );
      writeFileSync(
        join(root, "artifacts", "calibration_sessions", "cam1_session", "manifest.json"),
        JSON.stringify({ schema_version: "calibration.capture_session.v1", topology: "mono" }),
      );
      writeFileSync(
        join(root, "artifacts", "calibration", "cam1", "package.json"),
        JSON.stringify({ schema_version: "calibration.mono.v1", accepted: true }),
      );

      expect(collectCurrentCalibrationArtifacts(root)).toEqual([
        {
          name: "dfoptix_charuco_15mm_300dpi.json",
          path: "artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
          payload: { schema_version: "calibration.target_sheet.v1", accepted: true },
        },
        {
          name: "manifest.json",
          path: "artifacts/calibration_sessions/cam1_session/manifest.json",
          payload: { schema_version: "calibration.capture_session.v1", topology: "mono" },
        },
        {
          name: "package.json",
          path: "artifacts/calibration/cam1/package.json",
          payload: { schema_version: "calibration.mono.v1", accepted: true },
        },
      ]);
    } finally {
      rmSync(root, { recursive: true, force: true });
    }
  });
});

function makeTempRoot(): string {
  return join(process.cwd(), ".tmp-test", String(Date.now()), String(Math.random()).slice(2));
}
