#!/usr/bin/env bun
import { existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

type GateStatus = "passed" | "blocked" | "failed";

type GateResult = {
  id: string;
  label: string;
  status: GateStatus;
  detail: string;
  evidence: string;
  next?: string;
};

type JsonObject = Record<string, unknown>;

const repoRoot = resolve(import.meta.dirname, "..");
const defaultOutput = resolve(repoRoot, "docs", `local_physical_validation_status_${yyyymmdd(new Date())}.md`);

const args = parseArgs(Bun.argv.slice(2));
if (args.help) {
  printUsage();
  process.exit(0);
}

const gates = runValidationStatus();
const outputPath = args.output ?? defaultOutput;
writeReport(outputPath, gates);
for (const gate of gates) {
  console.log(`${gate.status.padEnd(7)} ${gate.label} - ${gate.detail}`);
}
console.log(`report=${outputPath}`);
process.exit(gates.every((gate) => gate.status === "passed") ? 0 : 1);

function runValidationStatus(): GateResult[] {
  const targetMetadata = targetMetadataCheck();
  const targetPrint = targetPrintCheck();
  const cam1 = monoPackageCheck("cam1", resolve(repoRoot, "artifacts/calibration/cam1/package.json"));
  const cam2 = monoPackageCheck("cam2", resolve(repoRoot, "artifacts/calibration/cam2/package.json"));
  const stereo = stereoPackageCheck(resolve(repoRoot, "artifacts/calibration/stereo_cam1_cam2/package.json"));
  const live3d = live3dPredictionCheck();
  return [targetMetadata, targetPrint, cam1, cam2, stereo, live3d];
}

function targetMetadataCheck(): GateResult {
  const path = resolve(repoRoot, "artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json");
  const payload = readJson(path);
  if (payload === undefined) {
    return {
      id: "target-metadata",
      label: "ChArUco target metadata",
      status: "blocked",
      detail: "target metadata is missing.",
      evidence: path,
      next: "Generate the target from the Calibration GUI Target tab.",
    };
  }
  const target = objectField(payload, "target");
  const squareMm = typeof target?.square_size_m === "number" ? target.square_size_m * 1000 : undefined;
  const accepted = payload.accepted === true && approximately(squareMm, 15, 0.001);
  return {
    id: "target-metadata",
    label: "ChArUco target metadata",
    status: accepted ? "passed" : "failed",
    detail: accepted ? "dfoptix ChArUco target metadata is accepted at 15.0 mm square size." : "target metadata is not accepted at 15.0 mm square size.",
    evidence: compactJson({
      path: displayPath(path),
      accepted: payload.accepted,
      profile: target?.profile,
      square_size_mm: squareMm,
      files: payload.files,
    }),
    next: accepted ? undefined : "Regenerate the target before printing.",
  };
}

function targetPrintCheck(): GateResult {
  const path = resolve(repoRoot, "artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json");
  const payload = readJson(path);
  if (payload === undefined) {
    return {
      id: "target-print",
      label: "Printed target measurement",
      status: "blocked",
      detail: "no recorded 15.0 mm print measurement was found.",
      evidence: displayPath(path),
      next: "Print the target SVG at 100%, measure one square, then record the measurement in this artifact.",
    };
  }
  const measured = numberField(payload, "measured_square_mm");
  const tolerance = numberField(payload, "tolerance_mm") ?? 0.2;
  const passed = payload.accepted === true && measured !== undefined && Math.abs(measured - 15) <= tolerance;
  return {
    id: "target-print",
    label: "Printed target measurement",
    status: passed ? "passed" : "failed",
    detail: passed ? `printed target measurement is ${measured} mm.` : "printed target measurement is missing or outside tolerance.",
    evidence: compactJson({ path: displayPath(path), measured_square_mm: measured, tolerance_mm: tolerance, accepted: payload.accepted }),
    next: passed ? undefined : "Fix printer scaling and reprint before camera capture.",
  };
}

function monoPackageCheck(cameraId: string, path: string): GateResult {
  const payload = readJson(path);
  if (payload === undefined) {
    return {
      id: `${cameraId}-mono`,
      label: `${cameraId} mono calibration`,
      status: "blocked",
      detail: `${cameraId} mono package is missing.`,
      evidence: displayPath(path),
      next: `Run the Calibration GUI ${cameraId === "cam1" ? "Cam1 Mono" : "Cam2 Mono"} flow through package verification.`,
    };
  }
  const quality = objectField(payload, "quality");
  const rms = numberField(quality, "rms_reprojection_px");
  const acceptedViews = numberField(quality, "accepted_view_count");
  const passed =
    payload.schema_version === "calibration.mono.v1" &&
    payload.accepted === true &&
    payload.dry_run === false &&
    payload.hardware_validated === true &&
    rms !== undefined &&
    rms <= 1.0 &&
    acceptedViews !== undefined &&
    acceptedViews >= 8;
  const blocked = payload.accepted === true && (payload.dry_run === true || payload.hardware_validated !== true);
  return {
    id: `${cameraId}-mono`,
    label: `${cameraId} mono calibration`,
    status: passed ? "passed" : blocked ? "blocked" : "failed",
    detail: passed
      ? `${cameraId} mono package is hardware validated.`
      : blocked
        ? `${cameraId} mono package is accepted but not hardware validated.`
        : `${cameraId} mono package does not satisfy the real calibration gate.`,
    evidence: compactJson({
      path: displayPath(path),
      accepted: payload.accepted,
      dry_run: payload.dry_run,
      hardware_validated: payload.hardware_validated,
      accepted_view_count: acceptedViews,
      rms_reprojection_px: rms,
    }),
    next: passed ? undefined : `Capture real ${cameraId} ChArUco frames, solve mono, and verify the package.`,
  };
}

function stereoPackageCheck(path: string): GateResult {
  const payload = readJson(path);
  if (payload === undefined) {
    return {
      id: "stereo",
      label: "Stereo calibration",
      status: "blocked",
      detail: "stereo package is missing.",
      evidence: displayPath(path),
      next: "Run the Calibration GUI Stereo flow after cam1 and cam2 mono packages are accepted.",
    };
  }
  const quality = objectField(payload, "quality");
  const rms = numberField(quality, "stereo_rms_reprojection_px");
  const pairCount = numberField(quality, "accepted_pair_count");
  const baseline = numberField(quality, "baseline_m") ?? stereoBaselineFromFile();
  const passed =
    payload.schema_version === "calibration.stereo.v1" &&
    payload.accepted === true &&
    payload.dry_run === false &&
    payload.hardware_validated === true &&
    rms !== undefined &&
    rms <= 2.0 &&
    pairCount !== undefined &&
    pairCount >= 12 &&
    baseline !== undefined &&
    baseline > 0;
  const blocked = payload.accepted === true && (payload.dry_run === true || payload.hardware_validated !== true);
  return {
    id: "stereo",
    label: "Stereo calibration",
    status: passed ? "passed" : blocked ? "blocked" : "failed",
    detail: passed
      ? "stereo package is hardware validated."
      : blocked
        ? "stereo package is accepted but not hardware validated."
        : "stereo package does not satisfy the physical validation gate.",
    evidence: compactJson({
      path: displayPath(path),
      accepted: payload.accepted,
      dry_run: payload.dry_run,
      hardware_validated: payload.hardware_validated,
      accepted_pair_count: pairCount,
      stereo_rms_reprojection_px: rms,
      baseline_m: baseline,
    }),
    next: passed ? undefined : "Capture real stereo ChArUco pairs, solve stereo, and verify the package.",
  };
}

function live3dPredictionCheck(): GateResult {
  const reports = latestLive3dReports();
  const passedReport = reports.find((report) => {
    const text = readFileSync(report.path, "utf-8");
    return text.includes("- Result: passed") && text.includes("prediction-ready");
  });
  if (passedReport !== undefined) {
    return {
      id: "live3d-prediction",
      label: "Live3D prediction-ready hardware run",
      status: "passed",
      detail: `${displayPath(passedReport.path)} reached prediction-ready.`,
      evidence: live3dEvidence(passedReport.path),
    };
  }
  const latest = reports[0];
  return {
    id: "live3d-prediction",
    label: "Live3D prediction-ready hardware run",
    status: "blocked",
    detail: "no Live3D hardware report has reached prediction-ready.",
    evidence: latest === undefined ? "No docs/live3d_hardware*.md reports found." : live3dEvidence(latest.path),
    next: "Put a visible tennis ball in both camera views and run apps/live3d verify:hardware until it passes.",
  };
}

function stereoBaselineFromFile(): number | undefined {
  const stereo = readJson(resolve(repoRoot, "artifacts/calibration/stereo_cam1_cam2/stereo.json"));
  return numberField(stereo, "baseline_m");
}

function latestLive3dReports(): Array<{ path: string; mtimeMs: number }> {
  const docsDir = resolve(repoRoot, "docs");
  if (!existsSync(docsDir)) return [];
  return readdirSync(docsDir)
    .filter((name) => /^live3d_hardware.*\.md$/u.test(name))
    .map((name) => {
      const path = join(docsDir, name);
      return { path, mtimeMs: statSync(path).mtimeMs };
    })
    .sort((left, right) => right.mtimeMs - left.mtimeMs);
}

function live3dEvidence(path: string): string {
  const text = readFileSync(path, "utf-8");
  const interesting = text
    .split("\n")
    .filter((line) =>
      [
        "- Result:",
        "- Error:",
        "- Max left detections:",
        "- Max right detections:",
        "- Max prediction samples:",
        "- Runtime 3D codes:",
      ].some((prefix) => line.startsWith(prefix)),
    );
  return [`report: ${displayPath(path)}`, ...interesting].join("\n");
}

function readJson(path: string): JsonObject | undefined {
  if (!existsSync(path)) return undefined;
  try {
    const value = JSON.parse(readFileSync(path, "utf-8")) as unknown;
    return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : undefined;
  } catch {
    return undefined;
  }
}

function objectField(payload: JsonObject | undefined, key: string): JsonObject | undefined {
  const value = payload?.[key];
  return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as JsonObject) : undefined;
}

function numberField(payload: JsonObject | undefined, key: string): number | undefined {
  const value = payload?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function approximately(value: number | undefined, expected: number, tolerance: number): boolean {
  return value !== undefined && Math.abs(value - expected) <= tolerance;
}

function compactJson(value: unknown): string {
  return JSON.stringify(value, null, 2);
}

function displayPath(path: string): string {
  const resolvedRoot = resolve(repoRoot);
  const resolvedPath = resolve(path);
  return resolvedPath === resolvedRoot || !resolvedPath.startsWith(`${resolvedRoot}/`)
    ? path
    : resolvedPath.slice(resolvedRoot.length + 1);
}

function writeReport(outputPath: string, gates: GateResult[]): void {
  mkdirSync(dirname(outputPath), { recursive: true });
  const result = gates.every((gate) => gate.status === "passed") ? "passed" : "incomplete";
  const lines = [
    "# Local Physical Validation Status",
    "",
    `- created_at: ${new Date().toISOString()}`,
    `- result: ${result}`,
    "",
    "## Gates",
    "",
    ...gates.map((gate) => `- ${gate.status}: ${gate.label} - ${gate.detail}`),
    "",
    "## Details",
    "",
    ...gates.flatMap((gate) => [
      `### ${gate.label}`,
      "",
      `- status: ${gate.status}`,
      `- detail: ${gate.detail}`,
      ...(gate.next === undefined ? [] : [`- next: ${gate.next}`]),
      "",
      "```text",
      gate.evidence,
      "```",
      "",
    ]),
  ];
  writeFileSync(outputPath, `${lines.join("\n")}\n`, "utf-8");
}

function parseArgs(args: string[]): { help: boolean; output?: string } {
  const parsed: { help: boolean; output?: string } = { help: false };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      parsed.help = true;
    } else if (arg === "--output") {
      const value = args[index + 1];
      if (value === undefined || value.startsWith("--")) {
        throw new Error("--output requires a path.");
      }
      parsed.output = resolve(repoRoot, value);
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return parsed;
}

function yyyymmdd(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function printUsage(): void {
  console.log(`Usage: bun scripts/physical-validation-status.ts [--output docs/local_physical_validation_status_YYYYMMDD.md]

Checks the physical TennisBot acceptance gates:
- generated ChArUco target metadata
- recorded printed target square measurement
- cam1 and cam2 real mono calibration packages
- real stereo calibration package
- Live3D hardware report reaching prediction-ready
`);
}
