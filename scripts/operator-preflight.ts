#!/usr/bin/env bun
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

type CheckStatus = "passed" | "failed";

type CheckResult = {
  id: string;
  label: string;
  status: CheckStatus;
  detail: string;
  evidence: string;
};

type CommandResult = {
  exitCode: number;
  stdout: string;
  stderr: string;
};

const repoRoot = resolve(import.meta.dirname, "..");
const defaultOutput = resolve(repoRoot, "docs", `local_runtime_preflight_${yyyymmdd(new Date())}.md`);

const args = parseArgs(Bun.argv.slice(2));
if (args.help) {
  printUsage();
  process.exit(0);
}

const checks = await runPreflight();
const outputPath = args.output ?? defaultOutput;
writeReport(outputPath, checks);
for (const check of checks) {
  console.log(`${check.status.padEnd(6)} ${check.label} - ${check.detail}`);
}
console.log(`report=${outputPath}`);
process.exit(checks.every((check) => check.status === "passed") ? 0 : 1);

async function runPreflight(): Promise<CheckResult[]> {
  const [live3d, yoloPackage, calibrationPackage, cameras] = await Promise.all([
    urlCheck("live3d", "Live3D surface", "http://127.0.0.1:5178/"),
    yoloPackageCheck(),
    calibrationPackageCheck(),
    cameraDeviceCheck(),
  ]);
  return [live3d, yoloPackage, calibrationPackage, cameras];
}

async function urlCheck(id: string, label: string, url: string): Promise<CheckResult> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1200);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return {
      id,
      label,
      status: response.ok ? "passed" : "failed",
      detail: response.ok ? `${url} returned ${response.status}.` : `${url} returned ${response.status}.`,
      evidence: response.statusText || String(response.status),
    };
  } catch (error) {
    return {
      id,
      label,
      status: "failed",
      detail: `${url} is not reachable.`,
      evidence: error instanceof Error ? error.message : String(error),
    };
  } finally {
    clearTimeout(timeout);
  }
}

async function yoloPackageCheck(): Promise<CheckResult> {
  const result = await runCommand(["uv", "run", "tennisbot-yolo", "package", "verify", "--path", "../../artifacts/models/tennis_ball_yolo"], {
    cwd: resolve(repoRoot, "tools/yolo"),
  });
  return {
    id: "yolo-package",
    label: "YOLO package",
    status: result.exitCode === 0 ? "passed" : "failed",
    detail: result.exitCode === 0 ? "artifacts/models/tennis_ball_yolo verified." : "YOLO package verification failed.",
    evidence: compactCommandEvidence(result),
  };
}

async function calibrationPackageCheck(): Promise<CheckResult> {
  const packageJsonPath = resolve(repoRoot, "artifacts/calibration/stereo_cam1_cam2/package.json");
  const payload = readJson(packageJsonPath);
  let accepted = false;
  accepted = payload?.accepted === true && payload?.package_kind === "stereo";
  return {
    id: "calibration-package",
    label: "Stereo calibration package",
    status: accepted ? "passed" : "failed",
    detail:
      accepted
        ? "artifacts/calibration/stereo_cam1_cam2 is present as an accepted stereo package."
        : "Stereo calibration package is missing or not accepted.",
    evidence:
      payload === undefined
        ? `missing ${displayPath(packageJsonPath)}`
        : JSON.stringify(
            {
              path: displayPath(packageJsonPath),
              accepted: payload.accepted,
              package_kind: payload.package_kind,
              schema_version: payload.schema_version,
            },
            null,
            2,
          ),
  };
}

function readJson(path: string): Record<string, unknown> | undefined {
  if (!existsSync(path)) return undefined;
  try {
    const value = JSON.parse(readFileSync(path, "utf-8")) as unknown;
    return value !== null && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined;
  } catch {
    return undefined;
  }
}

function displayPath(path: string): string {
  const resolvedRoot = resolve(repoRoot);
  const resolvedPath = resolve(path);
  return resolvedPath === resolvedRoot || !resolvedPath.startsWith(`${resolvedRoot}/`)
    ? path
    : resolvedPath.slice(resolvedRoot.length + 1);
}

async function cameraDeviceCheck(): Promise<CheckResult> {
  const detected = await runCommand(["bun", "scripts/detect-camera-devices.ts", "--json"], { cwd: repoRoot });
  let captureCount = 0;
  try {
    const payload = JSON.parse(detected.stdout) as { devices?: unknown };
    captureCount = Array.isArray(payload.devices) ? payload.devices.length : 0;
  } catch {
    captureCount = 0;
  }
  const passed = detected.exitCode === 0 && captureCount >= 2;
  return {
    id: "usb-cameras",
    label: "USB camera devices",
    status: passed ? "passed" : "failed",
    detail: passed
      ? `${captureCount} V4L2 capture devices detected.`
      : "Fewer than two V4L2 capture devices were detected.",
    evidence: compactCommandEvidence(detected),
  };
}

async function runCommand(command: string[], options: { cwd: string }): Promise<CommandResult> {
  const process = Bun.spawn(command, {
    cwd: options.cwd,
    env: processEnv(),
    stdin: "ignore",
    stdout: "pipe",
    stderr: "pipe",
  });
  const [stdout, stderr, exitCode] = await Promise.all([
    new Response(process.stdout).text(),
    new Response(process.stderr).text(),
    process.exited,
  ]);
  return { stdout, stderr, exitCode };
}

function processEnv(): Record<string, string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
}

function compactCommandEvidence(result: CommandResult): string {
  const text = [result.stdout.trim(), result.stderr.trim()].filter(Boolean).join("\n");
  return text === "" ? `exitCode=${result.exitCode}` : text;
}

function writeReport(outputPath: string, checks: CheckResult[]): void {
  mkdirSync(dirname(outputPath), { recursive: true });
  const status = checks.every((check) => check.status === "passed") ? "passed" : "failed";
  const lines = [
    "# Local Runtime Preflight",
    "",
    `- created_at: ${new Date().toISOString()}`,
    `- result: ${status}`,
    "",
    "## Checks",
    "",
    ...checks.map((check) => `- ${check.status}: ${check.label} - ${check.detail}`),
    "",
    "## Evidence",
    "",
    ...checks.flatMap((check) => [
      `### ${check.label}`,
      "",
      "```text",
      check.evidence,
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
  console.log(`Usage: bun scripts/operator-preflight.ts [--output docs/local_runtime_preflight_YYYYMMDD.md]

Checks local TennisBot operator readiness:
- Live3D URL at http://127.0.0.1:5178/
- YOLO runtime package verification
- Stereo calibration package verification
- At least two V4L2 capture devices
`);
}
