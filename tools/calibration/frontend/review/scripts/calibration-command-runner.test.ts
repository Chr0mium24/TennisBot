import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { describe, expect, test } from "bun:test";

import { createCalibrationCommandPlan } from "./calibration-command-runner";

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
});

function tempRoots(): { repoRoot: string; calibrationRoot: string } {
  const repoRoot = mkdtempSync(join(tmpdir(), "tennisbot-calibration-review-"));
  return { repoRoot, calibrationRoot: join(repoRoot, "tools", "calibration") };
}
