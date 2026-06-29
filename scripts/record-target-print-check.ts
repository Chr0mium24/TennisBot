#!/usr/bin/env bun
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

type Args = {
  help: boolean;
  measuredSquareMm?: number;
  toleranceMm: number;
  output: string;
  report: string;
};

type PrintCheckPayload = {
  schema_version: "calibration.target_print_check.v1";
  created_at: string;
  target_metadata: string;
  expected_square_mm: number;
  measured_square_mm: number;
  tolerance_mm: number;
  delta_mm: number;
  accepted: boolean;
  next_step: string;
};

const repoRoot = resolve(import.meta.dirname, "..");
const args = parseArgs(Bun.argv.slice(2));

if (args.help) {
  printUsage();
  process.exit(0);
}

if (args.measuredSquareMm === undefined) {
  throw new Error("--measured-square-mm is required.");
}

const expectedSquareMm = 15.0;
const deltaMm = Math.abs(args.measuredSquareMm - expectedSquareMm);
const accepted = deltaMm <= args.toleranceMm;
const createdAt = new Date().toISOString();
const payload: PrintCheckPayload = {
  schema_version: "calibration.target_print_check.v1",
  created_at: createdAt,
  target_metadata: "artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
  expected_square_mm: expectedSquareMm,
  measured_square_mm: args.measuredSquareMm,
  tolerance_mm: args.toleranceMm,
  delta_mm: Number(deltaMm.toFixed(4)),
  accepted,
  next_step: accepted
    ? "Proceed to cam1 mono, cam2 mono, and stereo calibration captures."
    : "Fix printer scaling and reprint the target before camera capture.",
};

mkdirSync(dirname(args.output), { recursive: true });
writeFileSync(args.output, `${JSON.stringify(payload, null, 2)}\n`, "utf-8");
writeReport(args.report, payload);

console.log(`accepted=${accepted}`);
console.log(`output=${args.output}`);
console.log(`report=${args.report}`);
process.exit(accepted ? 0 : 1);

function writeReport(path: string, payload: PrintCheckPayload): void {
  mkdirSync(dirname(path), { recursive: true });
  const lines = [
    "# Calibration Target Print Check",
    "",
    `- created_at: ${payload.created_at}`,
    `- accepted: ${payload.accepted}`,
    `- expected_square_mm: ${payload.expected_square_mm}`,
    `- measured_square_mm: ${payload.measured_square_mm}`,
    `- tolerance_mm: ${payload.tolerance_mm}`,
    `- delta_mm: ${payload.delta_mm}`,
    `- artifact: ${displayPath(args.output)}`,
    `- next_step: ${payload.next_step}`,
    "",
  ];
  writeFileSync(path, lines.join("\n"), "utf-8");
}

function parseArgs(values: string[]): Args {
  const parsed: Args = {
    help: false,
    toleranceMm: 0.2,
    output: resolve(repoRoot, "artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json"),
    report: resolve(repoRoot, "docs", `calibration_target_print_check_${yyyymmdd(new Date())}.md`),
  };
  for (let index = 0; index < values.length; index += 1) {
    const arg = values[index];
    if (arg === "--help" || arg === "-h") {
      parsed.help = true;
    } else if (arg === "--measured-square-mm") {
      parsed.measuredSquareMm = parsePositiveNumber(arg, values[index + 1]);
      index += 1;
    } else if (arg === "--tolerance-mm") {
      parsed.toleranceMm = parsePositiveNumber(arg, values[index + 1]);
      index += 1;
    } else if (arg === "--output") {
      parsed.output = parsePath(arg, values[index + 1]);
      index += 1;
    } else if (arg === "--report") {
      parsed.report = parsePath(arg, values[index + 1]);
      index += 1;
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return parsed;
}

function parsePositiveNumber(flag: string, value: string | undefined): number {
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value.`);
  }
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${flag} must be a positive number.`);
  }
  return parsed;
}

function parsePath(flag: string, value: string | undefined): string {
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a path.`);
  }
  return resolve(repoRoot, value);
}

function displayPath(path: string): string {
  const resolvedRoot = resolve(repoRoot);
  const resolvedPath = resolve(path);
  return resolvedPath === resolvedRoot || !resolvedPath.startsWith(`${resolvedRoot}/`)
    ? path
    : resolvedPath.slice(resolvedRoot.length + 1);
}

function yyyymmdd(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}${month}${day}`;
}

function printUsage(): void {
  console.log(`Usage: bun scripts/record-target-print-check.ts --measured-square-mm 15.0 [--tolerance-mm 0.2]

Records the physical print measurement for the generated ChArUco target:
- writes artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json
- writes docs/calibration_target_print_check_YYYYMMDD.md
`);
}
