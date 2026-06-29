import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, test } from "bun:test";

import {
  collectGeneratedCalibrationArtifacts,
  createCalibrationCommandPlan,
} from "./calibration-command-runner";

describe("calibration command runner", () => {
  test("plans whitelisted calibration commands without invoking a shell", () => {
    const roots = tempRoots();
    try {
      const plan = createCalibrationCommandPlan(
        [
          "uv run tennisbot-calibration capture inspect",
          "--session ../../artifacts/calibration_sessions/stereo_session",
          "--output-report ../../docs/calibration_capture_quality.md",
        ].join(" "),
        roots,
      );

      expect(plan.cwd).toBe(roots.calibrationRoot);
      expect(plan.argv).toEqual([
        "uv",
        "run",
        "tennisbot-calibration",
        "capture",
        "inspect",
        "--session",
        "../../artifacts/calibration_sessions/stereo_session",
        "--output-report",
        "../../docs/calibration_capture_quality.md",
      ]);
    } finally {
      rmSync(roots.repoRoot, { recursive: true, force: true });
    }
  });

  test("rejects commands outside the calibration whitelist", () => {
    const roots = tempRoots();
    try {
      expect(() => createCalibrationCommandPlan("rm -rf ../../artifacts", roots)).toThrow(
        "Only 'uv run tennisbot-calibration ...' commands are allowed.",
      );
      expect(() =>
        createCalibrationCommandPlan(
          "uv run tennisbot-calibration capture inspect --session ../../artifacts/session --output-report ../../README.md",
          roots,
        ),
      ).toThrow("--output-report must stay inside docs/.");
      expect(() =>
        createCalibrationCommandPlan(
          "uv run tennisbot-calibration capture mono --camera-id cam1 --device /tmp/video0 --output ../../artifacts/session",
          roots,
        ),
      ).toThrow("--device must be a /dev/videoN device path.");
    } finally {
      rmSync(roots.repoRoot, { recursive: true, force: true });
    }
  });

  test("collects generated JSON artifacts from command output paths", () => {
    const roots = tempRoots();
    try {
      const sessionDir = join(roots.repoRoot, "artifacts", "calibration_sessions", "stereo_session");
      mkdirSync(sessionDir, { recursive: true });
      writeFileSync(
        join(sessionDir, "inspection.json"),
        JSON.stringify({
          schema_version: "calibration.capture_inspection.v1",
          accepted: true,
        }),
      );
      const plan = createCalibrationCommandPlan(
        [
          "uv run tennisbot-calibration capture inspect",
          "--session ../../artifacts/calibration_sessions/stereo_session",
          "--output-report ../../docs/calibration_capture_quality.md",
        ].join(" "),
        roots,
      );

      expect(collectGeneratedCalibrationArtifacts(plan)).toEqual([
        {
          name: "inspection.json",
          path: "artifacts/calibration_sessions/stereo_session/inspection.json",
          payload: {
            schema_version: "calibration.capture_inspection.v1",
            accepted: true,
          },
        },
      ]);

      const verifyPlan = createCalibrationCommandPlan(
        "uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2",
        roots,
      );
      expect(
        collectGeneratedCalibrationArtifacts(
          verifyPlan,
          JSON.stringify({ schema_version: "calibration.package_verification.v1", accepted: true }),
        )[0],
      ).toMatchObject({
        name: "package-verification.json",
        path: "stdout:package-verification",
        payload: { schema_version: "calibration.package_verification.v1", accepted: true },
      });

      const targetDir = join(roots.repoRoot, "artifacts", "calibration_targets");
      mkdirSync(targetDir, { recursive: true });
      writeFileSync(
        join(targetDir, "target.json"),
        JSON.stringify({
          schema_version: "calibration.target_sheet.v1",
          accepted: true,
        }),
      );
      const targetPlan = createCalibrationCommandPlan(
        [
          "uv run tennisbot-calibration target charuco",
          "--output ../../artifacts/calibration_targets/target.png",
          "--output-report ../../docs/calibration_target.md",
          "--dpi 300",
          "--margin-mm 10",
        ].join(" "),
        roots,
      );
      expect(collectGeneratedCalibrationArtifacts(targetPlan)[0]).toMatchObject({
        name: "target.json",
        path: "artifacts/calibration_targets/target.json",
        payload: { schema_version: "calibration.target_sheet.v1", accepted: true },
      });

      writeFileSync(
        join(targetDir, "print_check.json"),
        JSON.stringify({
          schema_version: "calibration.target_print_check.v1",
          accepted: true,
        }),
      );
      const printCheckPlan = createCalibrationCommandPlan(
        [
          "uv run tennisbot-calibration target record-print-check",
          "--measured-square-mm 15.0",
          "--tolerance-mm 0.2",
          "--target-metadata ../../artifacts/calibration_targets/target.json",
          "--output ../../artifacts/calibration_targets/print_check.json",
          "--output-report ../../docs/calibration_target_print_check.md",
        ].join(" "),
        roots,
      );
      expect(collectGeneratedCalibrationArtifacts(printCheckPlan)[0]).toMatchObject({
        name: "print_check.json",
        path: "artifacts/calibration_targets/print_check.json",
        payload: { schema_version: "calibration.target_print_check.v1", accepted: true },
      });
    } finally {
      rmSync(roots.repoRoot, { recursive: true, force: true });
    }
  });
});

function tempRoots(): { repoRoot: string; calibrationRoot: string } {
  const repoRoot = mkdtempSync(join(tmpdir(), "tennisbot-calibration-review-"));
  return { repoRoot, calibrationRoot: join(repoRoot, "tools", "calibration") };
}
