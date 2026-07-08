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
  if (command === "sprites") {
    process.exit(await runYolo(["sprites", ...rest], { extra: "augment" }));
  }
  if (command === "augment") {
    process.exit(await runYolo(["augment", ...rest], { extra: "augment" }));
  }
  if (command === "benchmark") {
    process.exit(await runYolo(["benchmark", ...rest], detectExtraOptions(rest)));
  }
  if (command === "detect-gui") {
    process.exit(await runYolo(["detect-gui", ...rest], detectExtraOptions(rest)));
  }
  if (command === "detect-video") {
    process.exit(await runYolo(["detect-video", ...rest], detectExtraOptions(rest)));
  }
  throw new Error(`Unknown command: ${command}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("");
  printUsage();
  process.exit(2);
}

async function runYolo(args: string[], options: { extra?: string } = {}): Promise<number> {
  const command = ["uv", "run", "--project", yoloCwd];
  if (options.extra !== undefined) command.push("--extra", options.extra);
  command.push("tennisbot-yolo", ...args);
  const proc = Bun.spawn(command, {
    cwd: repoRoot,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
  return await waitForChild(proc);
}

function detectExtraOptions(args: string[]): { extra?: string } {
  if (args.includes("--dry-run") || args.includes("--help") || args.includes("-h")) {
    return {};
  }
  return { extra: "detect" };
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
  bun scripts/yolo.ts sprites extract [options]
  bun scripts/yolo.ts sprites review [options]
  bun scripts/yolo.ts augment copy-paste [options]
  bun scripts/yolo.ts benchmark tiles [options]
  bun scripts/yolo.ts detect-gui [options]
  bun scripts/yolo.ts detect-video <input-video> [options]

启动 YOLO 标注前端/后端。默认值:
  图片目录   tools/yolo/workspace/dataset/images
  标签目录   tools/yolo/workspace/dataset/labels
  排除列表   tools/yolo/workspace/dataset/excluded_images.txt
  地址       http://127.0.0.1:8765

常用命令:
  bun scripts/yolo.ts annotate
  bun scripts/yolo.ts annotate --port 8766
  bun scripts/yolo.ts annotate --images-root tools/yolo/workspace/dataset/images --labels-root tools/yolo/workspace/dataset/labels
  bun scripts/yolo.ts sprites extract
  bun scripts/yolo.ts sprites review
  bun scripts/yolo.ts augment copy-paste --config tools/yolo/configs/augmentation.toml
  bun scripts/yolo.ts benchmark tiles --dry-run
  bun scripts/yolo.ts benchmark tiles --output-markdown docs/current/yolo_tile_inference_benchmark_result_20260704.md
  bun scripts/yolo.ts detect-gui --tile
  bun scripts/yolo.ts detect-video input.mp4 --output runs/yolo-detect/input_boxes.mp4 --tile --overwrite

说明:
  annotate 使用 tools/yolo 的默认 uv 环境，不安装 torch、ultralytics 或 CUDA/NVIDIA Python 包。
  sprites 和 augment 使用 tools/yolo 的 augment extra，只安装 OpenCV/NumPy，不安装 torch、ultralytics 或 CUDA/NVIDIA Python 包。
  benchmark 实跑、纯 YOLO 相机检测 GUI 和离线视频导出使用 tools/yolo 的 detect extra。
`);
}
