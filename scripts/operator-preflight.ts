#!/usr/bin/env bun
import { mkdirSync, writeFileSync } from "node:fs";
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
  const [live3d, calibrationGui, yoloPackage, calibrationPackage, cameras] = await Promise.all([
    urlCheck("live3d", "Live3D surface", "http://127.0.0.1:5178/"),
    urlCheck("calibration-gui", "Calibration GUI surface", "http://127.0.0.1:5188/"),
    yoloPackageCheck(),
    calibrationPackageCheck(),
    cameraDeviceCheck(),
  ]);
  return [live3d, calibrationGui, yoloPackage, calibrationPackage, cameras];
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
  const result = await runCommand(
    [
      "uv",
      "run",
      "tennisbot-calibration",
      "package",
      "verify",
      "--path",
      "../../artifacts/calibration/stereo_cam1_cam2",
    ],
    { cwd: resolve(repoRoot, "tools/calibration") },
  );
  let accepted = false;
  try {
    const payload = JSON.parse(result.stdout) as { accepted?: unknown; package_kind?: unknown };
    accepted = payload.accepted === true && payload.package_kind === "stereo";
  } catch {
    accepted = false;
  }
  return {
    id: "calibration-package",
    label: "Stereo calibration package",
    status: result.exitCode === 0 && accepted ? "passed" : "failed",
    detail:
      result.exitCode === 0 && accepted
        ? "artifacts/calibration/stereo_cam1_cam2 verified as accepted stereo package."
        : "Stereo calibration package verification failed.",
    evidence: compactCommandEvidence(result),
  };
}

async function cameraDeviceCheck(): Promise<CheckResult> {
  const result = await runCommand(["v4l2-ctl", "--list-devices"], { cwd: repoRoot });
  const hasLeft = result.stdout.includes("/dev/video0");
  const hasRight = result.stdout.includes("/dev/video2");
  const passed = result.exitCode === 0 && hasLeft && hasRight;
  return {
    id: "usb-cameras",
    label: "USB camera devices",
    status: passed ? "passed" : "failed",
    detail: passed ? "/dev/video0 and /dev/video2 are present." : "Expected /dev/video0 and /dev/video2 were not both present.",
    evidence: result.exitCode === 0 ? result.stdout.trim() : compactCommandEvidence(result),
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
- Calibration GUI URL at http://127.0.0.1:5188/
- YOLO runtime package verification
- Stereo calibration package verification
- USB camera devices /dev/video0 and /dev/video2
`);
}
