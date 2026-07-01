#!/usr/bin/env bun
import { resolve } from "node:path";

type ForwardedSignal = "SIGINT" | "SIGTERM";

const repoRoot = resolve(import.meta.dirname, "..");
const stereoCwd = resolve(repoRoot, "tools/stereo");
const argv = Bun.argv.slice(2);

if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
  printUsage();
  process.exit(0);
}

try {
  const command = argv[0];
  const rest = argv.slice(1);
  if (command === "gui") {
    process.exit(await runStereoGui(rest));
  }
  throw new Error(`Unknown command: ${command}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("");
  printUsage();
  process.exit(2);
}

async function runStereoGui(args: string[]): Promise<number> {
  const command = [
    "uv",
    "run",
    ...detectExtraArgs(args),
    "tennisbot-stereo",
    "gui",
    ...args,
  ];
  const proc = Bun.spawn(command, {
    cwd: stereoCwd,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await waitForChild(proc);
}

function detectExtraArgs(args: string[]): string[] {
  if (args.includes("--dry-run") || detector(args) === "hsv" || args.includes("--help") || args.includes("-h")) {
    return [];
  }
  return ["--extra", "detect"];
}

function detector(args: string[]): string {
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--detector") {
      return args[index + 1] ?? "yolo";
    }
    if (arg.startsWith("--detector=")) {
      return arg.slice("--detector=".length);
    }
  }
  return "yolo";
}

async function waitForChild(proc: ReturnType<typeof Bun.spawn>): Promise<number> {
  const signals: ForwardedSignal[] = ["SIGINT", "SIGTERM"];
  const removers: Array<() => void> = [];
  let forceKillTimer: ReturnType<typeof setTimeout> | undefined;
  let terminating = false;

  for (const signal of signals) {
    const handler = () => {
      proc.kill(signal);
      if (terminating) return;
      terminating = true;
      forceKillTimer = setTimeout(() => proc.kill("SIGKILL"), 2000);
    };
    process.on(signal, handler);
    removers.push(() => process.off(signal, handler));
  }

  try {
    return await proc.exited;
  } finally {
    if (forceKillTimer !== undefined) clearTimeout(forceKillTimer);
    for (const remove of removers) remove();
  }
}

function printUsage(): void {
  console.log(`用法: bun scripts/stereo.ts gui [options]

启动本机 4K 双目 YOLO 坐标 GUI。默认值:
  相机       /dev/video0,/dev/video2
  采集       3840x2160@30 MJPG
  标定包     artifacts/calibration/stereo_cam1_cam2
  模型       artifacts/models/tennis_ball_yolo/model.pt

常用命令:
  bun scripts/stereo.ts gui
  bun scripts/stereo.ts gui --tile
  bun scripts/stereo.ts gui --dry-run
  bun scripts/stereo.ts gui --detector hsv
  bun scripts/stereo.ts gui --devices /dev/video0,/dev/video2

说明:
  GUI 显示的是左相机坐标系：x right, y down, z forward。
  YOLO 实跑会自动使用 tools/stereo 的 uv extra: detect。
`);
}
