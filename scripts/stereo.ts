#!/usr/bin/env bun
import { existsSync } from "node:fs";
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
  if (command === "gui" || command === "preview") {
    process.exit(await runStereoGui(rest));
  }
  if (command === "record") {
    process.exit(await runStereoRecord(rest));
  }
  if (command === "replay") {
    process.exit(await runStereoReplay(rest));
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

async function runStereoRecord(args: string[]): Promise<number> {
  const proc = Bun.spawn(["uv", "run", "tennisbot-stereo", "record", ...args], {
    cwd: stereoCwd,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await waitForChild(proc);
}

async function runStereoReplay(args: string[]): Promise<number> {
  const replayCwd = resolve(stereoCwd, "web/replay");
  if (!args.includes("--help") && !args.includes("-h")) {
    const installCode = await ensureReplayDependencies(replayCwd);
    if (installCode !== 0) return installCode;
    const build = Bun.spawn(["bun", "run", "build"], {
      cwd: replayCwd,
      env: process.env,
      stdin: "ignore",
      stdout: "inherit",
      stderr: "inherit",
    });
    const buildCode = await build.exited;
    if (buildCode !== 0) return buildCode;
  }
  const proc = Bun.spawn(["bun", "./src/server.ts", ...args], {
    cwd: replayCwd,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await waitForChild(proc);
}

async function ensureReplayDependencies(replayCwd: string): Promise<number> {
  if (existsSync(resolve(replayCwd, "node_modules/three"))) {
    return 0;
  }
  console.log("Installing stereo replay frontend dependencies...");
  const install = Bun.spawn(["bun", "install", "--frozen-lockfile"], {
    cwd: replayCwd,
    env: process.env,
    stdin: "ignore",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await install.exited;
}

function detectExtraArgs(args: string[]): string[] {
  if (args.includes("--dry-run") || args.includes("--help") || args.includes("-h")) {
    return [];
  }
  return ["--extra", "detect"];
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
  console.log(`用法:
  bun scripts/stereo.ts record [options]
  bun scripts/stereo.ts preview [options]
  bun scripts/stereo.ts gui [options]
  bun scripts/stereo.ts replay [options]

录制原始左右双目视频，或启动本机 4K 双目 YOLO 坐标 GUI。默认值:
  相机       /dev/video0,/dev/video2
  采集       3840x2160@30 MJPG
  标定包     artifacts/calibration/stereo_cam1_cam2
  模型       artifacts/models/tennis_ball_yolo/model.pt

常用命令:
  bun scripts/stereo.ts record
  bun scripts/stereo.ts record --duration 60
  bun scripts/stereo.ts record --dry-run
  bun scripts/stereo.ts preview
  bun scripts/stereo.ts gui
  bun scripts/stereo.ts gui --tile
  bun scripts/stereo.ts gui --dry-run
  bun scripts/stereo.ts gui --tile --record-run
  bun scripts/stereo.ts gui --devices /dev/video0,/dev/video2
  bun scripts/stereo.ts replay

说明:
  record 写入 runs/raw-stereo/<session>/left.mp4 和 right.mp4，不运行 YOLO。
  record 不传 --duration 时持续录制，预览窗口按 q 或 esc 停止。
  GUI 显示的是左相机坐标系：x right, y down, z forward。
  replay 会打开本地前端列出 runs/stereo 里的记录，时间段选择在浏览器中完成。
  YOLO 实跑会自动使用 tools/stereo 的 uv extra: detect。
`);
}
