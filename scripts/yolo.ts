#!/usr/bin/env bun
import { resolve } from "node:path";

type ForwardedSignal = "SIGINT" | "SIGTERM";

const repoRoot = resolve(import.meta.dirname, "..");
const yoloCwd = resolve(repoRoot, "tools/yolo");
const argv = Bun.argv.slice(2);

if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
  printUsage();
  process.exit(0);
}

try {
  const command = argv[0];
  const rest = argv.slice(1);
  if (command === "annotate") {
    process.exit(await runYolo(["annotate", ...rest]));
  }
  throw new Error(`Unknown command: ${command}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("");
  printUsage();
  process.exit(2);
}

async function runYolo(args: string[]): Promise<number> {
  const proc = Bun.spawn(["uv", "run", "tennisbot-yolo", ...args], {
    cwd: yoloCwd,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await waitForChild(proc);
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
  bun scripts/yolo.ts annotate [options]

启动 YOLO 标注前端/后端。默认值:
  图片目录   tools/yolo/yolo/dataset/images
  标签目录   tools/yolo/yolo/dataset/labels
  排除列表   tools/yolo/yolo/dataset/excluded_images.txt
  地址       http://127.0.0.1:8765

常用命令:
  bun scripts/yolo.ts annotate
  bun scripts/yolo.ts annotate --port 8766
  bun scripts/yolo.ts annotate --images-root tools/yolo/yolo/dataset/images --labels-root tools/yolo/yolo/dataset/labels

说明:
  annotate 使用 tools/yolo 的默认 uv 环境，不安装 torch、ultralytics 或 CUDA/NVIDIA Python 包。
  需要纯 YOLO 相机检测 GUI 时仍使用 tools/yolo 的 detect extra。
`);
}
