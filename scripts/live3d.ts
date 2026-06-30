#!/usr/bin/env bun
import { createWriteStream, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";

type Surface = {
  name: string;
  url: string;
  cwd: string;
  buildCommand: string[];
  serveCommand: string[];
  env: Record<string, string>;
  logPath: string;
};

type StartedSurface = {
  surface: Surface;
  process?: Bun.Subprocess<"ignore", "pipe", "pipe">;
  reused: boolean;
};

const repoRoot = resolve(import.meta.dirname, "..");
const surfaces: Surface[] = [
  {
    name: "Live3D",
    url: "http://127.0.0.1:5178/",
    cwd: resolve(repoRoot, "apps/live3d"),
    buildCommand: ["bun", "run", "build"],
    serveCommand: ["bun", "./scripts/serve.js"],
    env: { PORT: "5178" },
    logPath: "/tmp/tennisbot_live3d.log",
  },
];

const args = new Set(Bun.argv.slice(2));
const statusOnly = args.has("--status");
const skipBuild = args.has("--no-build");

if (args.has("--help") || args.has("-h")) {
  printUsage();
  process.exit(0);
}

if ([...args].some((arg) => !["--status", "--no-build"].includes(arg))) {
  printUsage();
  process.exit(2);
}

if (statusOnly) {
  const results = await Promise.all(surfaces.map(async (surface) => [surface, await isServing(surface.url)] as const));
  for (const [surface, serving] of results) {
    console.log(`${serving ? "ready" : "down"}  ${surface.name.padEnd(16)} ${surface.url}`);
  }
  process.exit(results.every(([, serving]) => serving) ? 0 : 1);
}

const started: StartedSurface[] = [];
for (const surface of surfaces) {
  started.push(await ensureSurface(surface));
}

console.log("");
console.log("Local TennisBot runtime surfaces:");
for (const item of started) {
  console.log(`- ${item.surface.name}: ${item.surface.url} (${item.reused ? "reused" : `pid ${item.process?.pid}`})`);
}
console.log("");
console.log("Use tools/calibration for camera brightness checks and mono/stereo calibration.");
console.log("Use Live3D after calibration and put a visible tennis ball in both camera views.");

const childProcesses = started.flatMap((item) => (item.process === undefined ? [] : [item.process]));
if (childProcesses.length === 0) {
  process.exit(0);
}

console.log("Press Ctrl+C to stop services started by this launcher.");
for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.on(signal, () => {
    for (const child of childProcesses) child.kill();
    process.exit(0);
  });
}

const firstExit = await Promise.race(
  childProcesses.map(async (child) => ({
    pid: child.pid,
    code: await child.exited,
  })),
);
for (const child of childProcesses) child.kill();
console.error(`Service process ${firstExit.pid} exited with code ${firstExit.code}.`);
process.exit(firstExit.code === 0 ? 0 : 1);

async function ensureSurface(surface: Surface): Promise<StartedSurface> {
  if (await isServing(surface.url)) {
    return { surface, reused: true };
  }

  if (!skipBuild) {
    await runChecked(surface, surface.buildCommand, "build");
  }

  mkdirSync(dirname(surface.logPath), { recursive: true });
  await Bun.write(surface.logPath, `${new Date().toISOString()} starting ${surface.name}\n`);
  const child = Bun.spawn(surface.serveCommand, {
    cwd: surface.cwd,
    env: { ...process.env, ...surface.env },
    stdin: "ignore",
    stdout: "pipe",
    stderr: "pipe",
  });
  void appendStream(surface.logPath, child.stdout);
  void appendStream(surface.logPath, child.stderr);

  await sleep(900);
  if (!(await isServing(surface.url))) {
    child.kill();
    throw new Error(`${surface.name} did not start at ${surface.url}. Check ${surface.logPath}.`);
  }
  return { surface, process: child, reused: false };
}

async function runChecked(surface: Surface, command: string[], label: string): Promise<void> {
  console.log(`${surface.name}: ${label} (${command.join(" ")})`);
  const result = Bun.spawn(command, {
    cwd: surface.cwd,
    env: process.env,
    stdin: "ignore",
    stdout: "inherit",
    stderr: "inherit",
  });
  const code = await result.exited;
  if (code !== 0) {
    throw new Error(`${surface.name} ${label} failed with exit code ${code}.`);
  }
}

async function appendStream(path: string, stream: ReadableStream<Uint8Array>): Promise<void> {
  const writer = createWriteStream(path, { flags: "a" });
  try {
    for await (const chunk of stream) {
      writer.write(Buffer.from(chunk));
    }
  } finally {
    writer.end();
  }
}

async function isServing(url: string): Promise<boolean> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 1000);
  try {
    const response = await fetch(url, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolveSleep) => setTimeout(resolveSleep, ms));
}

function printUsage(): void {
  console.log(`用法: bun scripts/live3d.ts [--status] [--no-build]

默认值:
  URL      http://127.0.0.1:5178/
  日志     /tmp/tennisbot_live3d.log
  行为     构建并启动缺失服务

启动或检查本机 TennisBot 操作员界面:
- Live3D at http://127.0.0.1:5178/

选项:
  --status    只检查 URL 是否已经可访问。
  --no-build  启动缺失服务时跳过前端构建。

标定和相机亮度检查使用:
  cd tools/calibration
  uv run camera-calib-lab camera brightness
  uv run camera-calib-lab capture stereo-charuco-auto-gui
`);
}
