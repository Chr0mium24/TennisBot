#!/usr/bin/env bun
import { existsSync, readdirSync, statSync } from "node:fs";
import { basename, relative, resolve } from "node:path";

type CameraId = "cam1" | "cam2";
type Mode = "capture-solve" | "capture-only" | "solve-only";

type MonoOptions = {
  cameraId: CameraId;
  mode: Mode;
  dryRun: boolean;
  device: string;
  views: string;
  session?: string;
  output: string;
  config: string;
  minViews: string;
  maxRmsPx: string;
};

type StereoOptions = {
  mode: Mode;
  dryRun: boolean;
  leftDevice: string;
  rightDevice: string;
  views: string;
  session?: string;
  output: string;
  leftMono: string;
  rightMono: string;
  config: string;
  minPairs: string;
  maxRmsPx: string;
};

type CommandStep = {
  label: string;
  args: string[];
};

type ForwardedSignal = "SIGINT" | "SIGTERM";

const repoRoot = resolve(import.meta.dirname, "..");
const calibrationCwd = resolve(repoRoot, "tools/calibration");
const calibrationCommand = ["uv", "run", "camera-calib-lab"];
const argv = Bun.argv.slice(2);

if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
  printUsage();
  process.exit(0);
}

try {
  const command = argv[0];
  const rest = argv.slice(1);
  if (command === "brightness") {
    process.exit(
      await runStep({ label: "camera brightness", args: ["camera", "brightness", ...brightnessArgs(rest)] }, false),
    );
  }
  if (command === "preview") {
    if (rest[0] === "--help" || rest[0] === "-h") {
      printPreviewUsage();
      process.exit(0);
    }
    process.exit(await runStep({ label: "camera preview", args: ["camera", "preview", ...previewArgs(rest)] }, false));
  }
  if (command === "mono") {
    process.exit(await runMono(rest));
  }
  if (command === "stereo") {
    process.exit(await runStereo(rest));
  }
  throw new Error(`Unknown command: ${command}`);
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("");
  printUsage();
  process.exit(2);
}

async function runMono(args: string[]): Promise<number> {
  const options = parseMonoOptions(args);
  const session = options.session ?? defaultSessionPath(options.mode, `${options.cameraId}_charuco`);
  const steps: CommandStep[] = [];
  if (options.mode !== "solve-only") {
    if (options.mode === "capture-solve" && existsSync(session)) {
      throw new Error(`Session path already exists: ${session}. Pass --session to a new path or use --solve-only.`);
    }
    steps.push({
      label: `${options.cameraId} capture`,
      args: [
        "capture",
        "charuco-auto-gui",
        "--config",
        options.config,
        "--device",
        options.device,
        "--views",
        options.views,
        "--output",
        session,
      ],
    });
  }
  if (options.mode !== "capture-only") {
    steps.push({
      label: `${options.cameraId} solve`,
      args: [
        "solve",
        "mono",
        "--config",
        options.config,
        "--session",
        session,
        "--output",
        options.output,
        "--camera-id",
        options.cameraId,
        "--min-views",
        options.minViews,
        "--max-rms-px",
        options.maxRmsPx,
      ],
    });
  }
  return runSteps(steps, options.dryRun);
}

async function runStereo(args: string[]): Promise<number> {
  const options = parseStereoOptions(args);
  const session = options.session ?? defaultSessionPath(options.mode, "stereo_charuco");
  const steps: CommandStep[] = [];
  if (options.mode !== "solve-only") {
    if (options.mode === "capture-solve" && existsSync(session)) {
      throw new Error(`Session path already exists: ${session}. Pass --session to a new path or use --solve-only.`);
    }
    steps.push({
      label: "stereo capture",
      args: [
        "capture",
        "stereo-charuco-auto-gui",
        "--config",
        options.config,
        "--left-device",
        options.leftDevice,
        "--right-device",
        options.rightDevice,
        "--views",
        options.views,
        "--output",
        session,
      ],
    });
  }
  if (options.mode !== "capture-only") {
    steps.push({
      label: "stereo solve",
      args: [
        "solve",
        "stereo",
        "--config",
        options.config,
        "--session",
        session,
        "--left-mono",
        options.leftMono,
        "--right-mono",
        options.rightMono,
        "--output",
        options.output,
        "--left-camera-id",
        "cam1",
        "--right-camera-id",
        "cam2",
        "--min-pairs",
        options.minPairs,
        "--max-rms-px",
        options.maxRmsPx,
      ],
    });
  }
  return runSteps(steps, options.dryRun);
}

async function runSteps(steps: CommandStep[], dryRun: boolean): Promise<number> {
  for (const step of steps) {
    const code = await runStep(step, dryRun);
    if (code !== 0) return code;
  }
  return 0;
}

async function runStep(step: CommandStep, dryRun: boolean): Promise<number> {
  const command = [...calibrationCommand, ...step.args];
  if (dryRun) {
    console.log(`${step.label}:`);
    console.log(`  cd ${displayPath(calibrationCwd)}`);
    console.log(`  ${displayCommand(command)}`);
    return 0;
  }
  const proc = Bun.spawn(command, {
    cwd: calibrationCwd,
    env: processEnv(),
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

function parseMonoOptions(args: string[]): MonoOptions {
  if (args.length === 0 || args[0] === "--help" || args[0] === "-h") {
    printMonoUsage();
    process.exit(0);
  }
  const cameraId = parseCameraId(args[0]);
  const parsed: MonoOptions = {
    cameraId,
    mode: "capture-solve",
    dryRun: false,
    device: cameraId === "cam1" ? "/dev/video0" : "/dev/video2",
    views: "30",
    output: artifactPath(cameraId),
    config: configPath(),
    minViews: "8",
    maxRmsPx: "1.0",
  };
  for (let index = 1; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--capture-only") {
      parsed.mode = setMode(parsed.mode, "capture-only");
    } else if (arg === "--solve-only") {
      parsed.mode = setMode(parsed.mode, "solve-only");
    } else if (arg === "--dry-run") {
      parsed.dryRun = true;
    } else if (arg === "--device") {
      parsed.device = requireValue(args, ++index, arg);
    } else if (arg === "--views") {
      parsed.views = requirePositiveInteger(args, ++index, arg);
    } else if (arg === "--session") {
      parsed.session = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--output") {
      parsed.output = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--config") {
      parsed.config = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--min-views") {
      parsed.minViews = requirePositiveInteger(args, ++index, arg);
    } else if (arg === "--max-rms-px") {
      parsed.maxRmsPx = requirePositiveNumber(args, ++index, arg);
    } else {
      throw new Error(`Unknown mono option: ${arg}`);
    }
  }
  return parsed;
}

function parseStereoOptions(args: string[]): StereoOptions {
  if (args[0] === "--help" || args[0] === "-h") {
    printStereoUsage();
    process.exit(0);
  }
  const parsed: StereoOptions = {
    mode: "capture-solve",
    dryRun: false,
    leftDevice: "/dev/video0",
    rightDevice: "/dev/video2",
    views: "30",
    output: artifactPath("stereo_cam1_cam2"),
    leftMono: artifactPath("cam1"),
    rightMono: artifactPath("cam2"),
    config: configPath(),
    minPairs: "12",
    maxRmsPx: "2.0",
  };
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--capture-only") {
      parsed.mode = setMode(parsed.mode, "capture-only");
    } else if (arg === "--solve-only") {
      parsed.mode = setMode(parsed.mode, "solve-only");
    } else if (arg === "--dry-run") {
      parsed.dryRun = true;
    } else if (arg === "--devices") {
      const [left, right] = requireValue(args, ++index, arg).split(",");
      if (!left || !right) throw new Error("--devices requires <left,right>");
      parsed.leftDevice = left;
      parsed.rightDevice = right;
    } else if (arg === "--left-device") {
      parsed.leftDevice = requireValue(args, ++index, arg);
    } else if (arg === "--right-device") {
      parsed.rightDevice = requireValue(args, ++index, arg);
    } else if (arg === "--views") {
      parsed.views = requirePositiveInteger(args, ++index, arg);
    } else if (arg === "--session") {
      parsed.session = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--output") {
      parsed.output = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--left-mono") {
      parsed.leftMono = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--right-mono") {
      parsed.rightMono = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--config") {
      parsed.config = pathFromRepo(requireValue(args, ++index, arg));
    } else if (arg === "--min-pairs") {
      parsed.minPairs = requirePositiveInteger(args, ++index, arg);
    } else if (arg === "--max-rms-px") {
      parsed.maxRmsPx = requirePositiveNumber(args, ++index, arg);
    } else {
      throw new Error(`Unknown stereo option: ${arg}`);
    }
  }
  return parsed;
}

function brightnessArgs(args: string[]): string[] {
  const hasDeviceOverride = args.some((arg) => arg === "--devices" || arg.startsWith("--devices="));
  if (args.includes("--help") || args.includes("-h") || hasDeviceOverride) {
    return args;
  }
  return ["--devices", "/dev/video0,/dev/video2", ...args];
}

function previewArgs(args: string[]): string[] {
  const [target, ...rest] = args;
  if (target === "cam1") {
    return previewMonoArgs("/dev/video0", rest);
  }
  if (target === "cam2") {
    return previewMonoArgs("/dev/video2", rest);
  }
  if (target === "stereo") {
    return previewStereoArgs(rest);
  }
  if (target !== undefined && !target.startsWith("-")) {
    throw new Error(`Unknown preview target: ${target}. Use cam1, cam2, or stereo.`);
  }
  return previewStereoArgs(args);
}

function previewMonoArgs(defaultDevice: string, args: string[]): string[] {
  if (hasAnyOption(args, ["--device", "--devices"])) {
    return args;
  }
  return ["--device", defaultDevice, ...args];
}

function previewStereoArgs(args: string[]): string[] {
  if (hasAnyOption(args, ["--device", "--devices"])) {
    return args;
  }
  return ["--devices", "/dev/video0,/dev/video2", ...args];
}

function hasAnyOption(args: string[], names: string[]): boolean {
  return args.some((arg) => names.some((name) => arg === name || arg.startsWith(`${name}=`)));
}

function defaultSessionPath(mode: Mode, prefix: string): string {
  if (mode === "solve-only") {
    return latestSessionPath(prefix);
  }
  return resolve(calibrationCwd, "captures/local", `${prefix}_${timestamp()}`);
}

function latestSessionPath(prefix: string): string {
  const dir = resolve(calibrationCwd, "captures/local");
  if (!existsSync(dir)) {
    throw new Error(`No captures directory found at ${dir}; pass --session for --solve-only.`);
  }
  const candidates = readdirSync(dir)
    .map((name) => resolve(dir, name))
    .filter((path) => basename(path).startsWith(prefix) && existsSync(resolve(path, "manifest.json")))
    .sort((left, right) => statSync(right).mtimeMs - statSync(left).mtimeMs);
  if (candidates.length === 0) {
    throw new Error(`No capture session found for prefix ${prefix}; pass --session for --solve-only.`);
  }
  return candidates[0];
}

function setMode(current: Mode, next: Mode): Mode {
  if (current !== "capture-solve" && current !== next) {
    throw new Error("--capture-only and --solve-only are mutually exclusive");
  }
  return next;
}

function parseCameraId(value: string): CameraId {
  if (value === "cam1" || value === "cam2") return value;
  throw new Error("mono requires camera id cam1 or cam2");
}

function requireValue(args: string[], index: number, flag: string): string {
  const value = args[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value`);
  }
  return value;
}

function requirePositiveInteger(args: string[], index: number, flag: string): string {
  const value = requireValue(args, index, flag);
  if (!/^[1-9]\d*$/.test(value)) {
    throw new Error(`${flag} must be a positive integer`);
  }
  return value;
}

function requirePositiveNumber(args: string[], index: number, flag: string): string {
  const value = requireValue(args, index, flag);
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new Error(`${flag} must be a positive number`);
  }
  return value;
}

function configPath(): string {
  return resolve(calibrationCwd, "configs/dfoptix_charuco_15mm_capture.yaml");
}

function artifactPath(name: string): string {
  return resolve(repoRoot, "artifacts/calibration", name);
}

function pathFromRepo(value: string): string {
  return value.startsWith("/") ? value : resolve(repoRoot, value);
}

function timestamp(): string {
  const now = new Date();
  return [
    now.getFullYear(),
    twoDigits(now.getMonth() + 1),
    twoDigits(now.getDate()),
    "_",
    twoDigits(now.getHours()),
    twoDigits(now.getMinutes()),
    twoDigits(now.getSeconds()),
    "_",
    localTimeZoneAbbreviation(now),
  ].join("");
}

function twoDigits(value: number): string {
  return String(value).padStart(2, "0");
}

function localTimeZoneAbbreviation(date: Date): string {
  const match = date.toString().match(/\(([^)]+)\)$/);
  const timeZoneName = match?.[1];
  if (timeZoneName !== undefined) {
    const abbreviation = timeZoneName
      .split(/\s+/)
      .map((word) => word.slice(0, 1))
      .join("")
      .replace(/[^A-Za-z0-9]/g, "");
    if (abbreviation.length > 0) return abbreviation;
  }

  const offsetMinutes = -date.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "p" : "m";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = Math.floor(absoluteMinutes / 60);
  const minutes = absoluteMinutes % 60;
  return `UTC${sign}${twoDigits(hours)}${twoDigits(minutes)}`;
}

function processEnv(): Record<string, string> {
  return Object.fromEntries(Object.entries(process.env).filter((entry): entry is [string, string] => entry[1] !== undefined));
}

function displayPath(path: string): string {
  const resolved = resolve(path);
  return resolved.startsWith(`${repoRoot}/`) ? resolved.slice(repoRoot.length + 1) : resolved;
}

function displayCommand(command: string[]): string {
  return command.map((value) => shellWord(displayCommandArg(value))).join(" ");
}

function displayCommandArg(value: string): string {
  if (!value.startsWith("/")) return value;
  const resolved = resolve(value);
  if (!resolved.startsWith(`${repoRoot}/`)) return value;
  return relative(calibrationCwd, resolved) || ".";
}

function shellWord(value: string): string {
  return /^[A-Za-z0-9_./:=,@+-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
}

function printUsage(): void {
  console.log(`用法:
  bun scripts/calib.ts brightness [camera brightness options]
  bun scripts/calib.ts preview [cam1|cam2|stereo] [camera preview options]
  bun scripts/calib.ts mono cam1 [options]
  bun scripts/calib.ts mono cam2 [options]
  bun scripts/calib.ts stereo [options]

常用:
  bun scripts/calib.ts brightness
  bun scripts/calib.ts preview
  bun scripts/calib.ts mono cam1
  bun scripts/calib.ts mono cam2
  bun scripts/calib.ts stereo

默认:
  brightness devices: /dev/video0,/dev/video2
  preview devices: /dev/video0,/dev/video2

选项:
  --capture-only   只采集，不求解
  --solve-only     只求解，默认使用最新匹配 session
  --dry-run        mono/stereo 只打印命令；brightness/preview 不采集图像帧

查看子命令:
  bun scripts/calib.ts preview --help
  bun scripts/calib.ts mono --help
  bun scripts/calib.ts stereo --help
`);
}

function printPreviewUsage(): void {
  console.log(`用法:
  bun scripts/calib.ts preview [options]
  bun scripts/calib.ts preview cam1 [options]
  bun scripts/calib.ts preview cam2 [options]
  bun scripts/calib.ts preview stereo [options]

默认:
  preview: /dev/video0,/dev/video2
  cam1: /dev/video0
  cam2: /dev/video2
  resolution: 3840x2160 @ 30 FPS

选项:
  --device <path>
  --devices <left,right>
  --shutter <n>
  --exposure <n>
  --gain <n>
  --brightness <n>
  --auto-exposure
  --width <px>
  --height <px>
  --fps <n>
  --dry-run

窗口:
  滑条调 shutter/exposure_time_absolute、gain 和 brightness。
  q 或 esc 退出。
`);
}

function printMonoUsage(): void {
  console.log(`用法:
  bun scripts/calib.ts mono cam1 [options]
  bun scripts/calib.ts mono cam2 [options]

默认:
  cam1 device: /dev/video0
  cam2 device: /dev/video2
  session: tools/calibration/captures/local/<cam>_charuco_<local_timestamp>
  output: artifacts/calibration/<cam>

选项:
  --device <path>
  --views <n>
  --session <path>
  --output <path>
  --min-views <n>
  --max-rms-px <px>
  --capture-only
  --solve-only
  --dry-run
`);
}

function printStereoUsage(): void {
  console.log(`用法:
  bun scripts/calib.ts stereo [options]

默认:
  devices: /dev/video0,/dev/video2
  session: tools/calibration/captures/local/stereo_charuco_<local_timestamp>
  left mono: artifacts/calibration/cam1
  right mono: artifacts/calibration/cam2
  output: artifacts/calibration/stereo_cam1_cam2

选项:
  --devices <left,right>
  --left-device <path>
  --right-device <path>
  --views <n>
  --session <path>
  --left-mono <path>
  --right-mono <path>
  --output <path>
  --min-pairs <n>
  --max-rms-px <px>
  --capture-only
  --solve-only
  --dry-run
`);
}
