#!/usr/bin/env bun

import { resolve } from "node:path";

type ForwardedSignal = "SIGINT" | "SIGTERM";

type Options = {
  command: "run" | "task";
  dryRun: boolean;
  withManager: boolean;
  record: boolean;
  taskId?: string;
  singleTask: boolean;
  logRoot: string;
  session?: string;
  video: boolean;
  chassisLog: boolean;
  yoloLog: boolean;
  targetLog: boolean;
  eventLog: boolean;
  autoSource: boolean;
  setupFiles: string[];
  tile?: boolean;
  devices?: string;
  leftDevice?: string;
  rightDevice?: string;
  width?: string;
  height?: string;
  fps?: string;
  model?: string;
  calibrationPackage?: string;
  yoloDevice?: string;
  extraParams: string[];
};

const repoRoot = resolve(import.meta.dirname, "..");
const argv = Bun.argv.slice(2);

if (argv.length === 0 || argv[0] === "--help" || argv[0] === "-h") {
  printUsage();
  process.exit(0);
}

try {
  const options = parseOptions(argv);
  process.exit(await run(options));
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  console.error("");
  printUsage();
  process.exit(2);
}

async function run(options: Options): Promise<number> {
  const visionRuntime = wrapRosCommand(buildVisionRuntimeCommand(options), options);
  const managerCommand = buildManagerCommand(options);
  const manager = managerCommand === undefined ? undefined : wrapRosCommand(managerCommand, options);

  if (options.dryRun) {
    if (manager !== undefined) console.log(displayCommand(manager));
    console.log(displayCommand(visionRuntime));
    return 0;
  }

  const procs: Array<ReturnType<typeof Bun.spawn>> = [];
  if (manager !== undefined) {
    procs.push(spawn(manager));
  }
  const visionRuntimeProc = spawn(visionRuntime);
  procs.push(visionRuntimeProc);

  const removeSignals = forwardSignals(procs);
  try {
    const exits = procs.map((proc, index) => proc.exited.then((code) => ({ index, code })));
    const first = await Promise.race(exits);
    for (const [index, proc] of procs.entries()) {
      if (index !== first.index) terminate(proc);
    }
    await Promise.allSettled(procs.map((proc) => proc.exited));
    return first.code;
  } finally {
    removeSignals();
  }
}

function buildVisionRuntimeCommand(options: Options): string[] {
  const params: string[] = [];
  addParam(params, "runtime_log_enabled", boolValue(options.record));
  addParam(params, "runtime_log_root", options.logRoot);
  addParam(params, "runtime_log_video", boolValue(options.video));
  addParam(params, "runtime_log_chassis", boolValue(options.chassisLog));
  addParam(params, "runtime_log_yolo", boolValue(options.yoloLog));
  addParam(params, "runtime_log_targets", boolValue(options.targetLog));
  addParam(params, "runtime_log_events", boolValue(options.eventLog));
  addParam(params, "single_task_mode", boolValue(options.singleTask));
  addParam(params, "single_task_shutdown_on_complete", boolValue(options.singleTask));
  if (options.session !== undefined) addParam(params, "runtime_log_session", options.session);
  if (options.taskId !== undefined) addParam(params, "initial_task_id", options.taskId);
  if (options.tile !== undefined) addParam(params, "tile", boolValue(options.tile));
  if (options.leftDevice !== undefined) addParam(params, "left_device", options.leftDevice);
  if (options.rightDevice !== undefined) addParam(params, "right_device", options.rightDevice);
  if (options.devices !== undefined) {
    const devices = parseDevices(options.devices);
    addParam(params, "left_device", devices[0]);
    addParam(params, "right_device", devices[1]);
  }
  if (options.width !== undefined) addParam(params, "width", options.width);
  if (options.height !== undefined) addParam(params, "height", options.height);
  if (options.fps !== undefined) addParam(params, "fps", options.fps);
  if (options.model !== undefined) addParam(params, "model_path", options.model);
  if (options.calibrationPackage !== undefined) {
    addParam(params, "calibration_package", options.calibrationPackage);
  }
  if (options.yoloDevice !== undefined) addParam(params, "yolo_device", options.yoloDevice);
  for (const item of options.extraParams) {
    params.push("-p", item);
  }

  return [
    "ros2",
    "run",
    "tennisbot_headless_vision",
    "headless_vision_node",
    "--ros-args",
    ...params,
  ];
}

function buildManagerCommand(options: Options): string[] | undefined {
  if (!options.withManager) return undefined;
  return ["ros2", "launch", "target_manager", "target_manager.launch.py"];
}

function parseOptions(args: string[]): Options {
  const command = args[0];
  if (command !== "run" && command !== "task") {
    throw new Error(`Unknown command: ${command}`);
  }
  const options: Options = {
    command,
    dryRun: false,
    withManager: true,
    record: command === "task",
    singleTask: command === "task",
    logRoot: "runs/vision-runtime",
    video: true,
    chassisLog: true,
    yoloLog: true,
    targetLog: true,
    eventLog: true,
    autoSource: true,
    setupFiles: defaultSetupFiles(),
    extraParams: [],
  };

  for (let index = 1; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    }
    if (arg === "--dry-run") options.dryRun = true;
    else if (arg === "--with-manager") options.withManager = true;
    else if (arg === "--no-manager") options.withManager = false;
    else if (arg === "--record") options.record = true;
    else if (arg === "--no-record") options.record = false;
    else if (arg === "--single-task") options.singleTask = true;
    else if (arg === "--continuous") options.singleTask = false;
    else if (arg === "--tile") options.tile = true;
    else if (arg === "--no-tile") options.tile = false;
    else if (arg === "--no-video") options.video = false;
    else if (arg === "--no-chassis-log") options.chassisLog = false;
    else if (arg === "--no-yolo-log") options.yoloLog = false;
    else if (arg === "--no-target-log") options.targetLog = false;
    else if (arg === "--no-event-log") options.eventLog = false;
    else if (arg === "--auto-source") options.autoSource = true;
    else if (arg === "--no-auto-source") options.autoSource = false;
    else if (arg === "--clear-setup-files") options.setupFiles = [];
    else if (arg === "--setup-file") options.setupFiles.push(takeValue(args, ++index, arg));
    else if (arg === "--task-id") options.taskId = takeValue(args, ++index, arg);
    else if (arg === "--log-root") options.logRoot = takeValue(args, ++index, arg);
    else if (arg === "--session") options.session = takeValue(args, ++index, arg);
    else if (arg === "--devices") options.devices = takeValue(args, ++index, arg);
    else if (arg === "--left-device") options.leftDevice = takeValue(args, ++index, arg);
    else if (arg === "--right-device") options.rightDevice = takeValue(args, ++index, arg);
    else if (arg === "--width") options.width = takeValue(args, ++index, arg);
    else if (arg === "--height") options.height = takeValue(args, ++index, arg);
    else if (arg === "--fps") options.fps = takeValue(args, ++index, arg);
    else if (arg === "--model") options.model = takeValue(args, ++index, arg);
    else if (arg === "--calibration-package") options.calibrationPackage = takeValue(args, ++index, arg);
    else if (arg === "--yolo-device") options.yoloDevice = takeValue(args, ++index, arg);
    else if (arg === "--param") options.extraParams.push(takeValue(args, ++index, arg));
    else throw new Error(`Unknown option: ${arg}`);
  }

  if (options.command === "task" && options.taskId === undefined) {
    throw new Error("task command requires --task-id");
  }
  return options;
}

function defaultSetupFiles(): string[] {
  return [
    process.env.ROS_SETUP ?? "/opt/ros/humble/setup.bash",
    process.env.TENNISBOT_CONTROL_SETUP ?? "/home/cr/tennis_robot_ws/install/setup.bash",
    process.env.TENNISBOT_LOCAL_SETUP ?? resolve(repoRoot, "install/setup.bash"),
  ];
}

function wrapRosCommand(command: string[], options: Options): string[] {
  if (!options.autoSource) return command;
  const sourcePrefix = options.setupFiles
    .filter((item) => item.trim().length > 0)
    .map((item) => `source ${shellQuote(item)} && `)
    .join("");
  return ["bash", "-lc", `${sourcePrefix}exec ${command.map(shellQuote).join(" ")}`];
}

function addParam(params: string[], name: string, value: string): void {
  params.push("-p", `${name}:=${value}`);
}

function boolValue(value: boolean): string {
  return value ? "true" : "false";
}

function takeValue(args: string[], index: number, option: string): string {
  const value = args[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${option} requires a value`);
  }
  return value;
}

function parseDevices(value: string): [string, string] {
  const devices = value.split(",").map((item) => item.trim()).filter(Boolean);
  if (devices.length !== 2) {
    throw new Error("--devices requires exactly two comma-separated devices");
  }
  return [devices[0], devices[1]];
}

function spawn(command: string[]): ReturnType<typeof Bun.spawn> {
  return Bun.spawn(command, {
    cwd: repoRoot,
    env: process.env,
    stdin: "inherit",
    stdout: "inherit",
    stderr: "inherit",
  });
}

function forwardSignals(procs: Array<ReturnType<typeof Bun.spawn>>): () => void {
  const signals: ForwardedSignal[] = ["SIGINT", "SIGTERM"];
  const removers: Array<() => void> = [];
  for (const signal of signals) {
    const handler = () => {
      for (const proc of procs) terminate(proc, signal);
    };
    process.on(signal, handler);
    removers.push(() => process.off(signal, handler));
  }
  return () => {
    for (const remove of removers) remove();
  };
}

function terminate(proc: ReturnType<typeof Bun.spawn>, signal: ForwardedSignal = "SIGTERM"): void {
  proc.kill(signal);
  const timer = setTimeout(() => proc.kill("SIGKILL"), 2000);
  timer.unref?.();
}

function displayCommand(command: string[]): string {
  return command.map(shellQuote).join(" ");
}

function shellQuote(value: string): string {
  return /^[A-Za-z0-9_./:=,-]+$/.test(value) ? value : `'${value.replace(/'/g, "'\\''")}'`;
}

function printUsage(): void {
  console.log(`用法:
  bun scripts/headless.ts run [options]
  bun scripts/headless.ts task --task-id <id> [options]

主链路入口:
  run   启动 vision runtime，可选启动外部 target_manager，可选记录运行日志
  task  用指定 task_id 启动单次任务，默认开启日志，任务结束后 vision runtime 节点退出

常用命令:
  bun scripts/headless.ts run
  bun scripts/headless.ts run --record --session test01 --tile
  bun scripts/headless.ts task --task-id 42 --session catch42 --tile
  bun scripts/headless.ts task --task-id 42 --no-video
  bun scripts/headless.ts run --dry-run --record --devices /dev/video0,/dev/video2

选项:
  --record / --no-record              开关 runs/vision-runtime 日志
  --log-root <path>                   日志根目录，默认 runs/vision-runtime
  --session <name>                    日志会话名，默认自动时间戳
  --no-video                          不写 left.mp4/right.mp4
  --no-chassis-log                    不写 chassis.ndjson
  --no-yolo-log                       不写 frames/detections/observations
  --no-target-log                     不写 targets.ndjson
  --task-id <id>                      初始或单次任务 task_id
  --single-task / --continuous        单任务或连续任务模式
  --with-manager / --no-manager       是否同时启动外部 target_manager，默认启动
  --auto-source / --no-auto-source    是否自动 source ROS/control/local setup，默认开启
  --setup-file <path>                 追加一个 setup.bash，可重复
  --clear-setup-files                 清空默认 setup 列表，配合 --setup-file 使用
  --tile / --no-tile                  覆盖 YOLO tiled 推理
  --devices <left,right>              覆盖双目设备
  --param <name:=value>               透传 ROS 参数，可重复

说明:
  运行阶段默认自动 source ROS、控制工作区和本仓库 install；构建阶段仍需 source 后 colcon build。
  默认 setup 可用 ROS_SETUP、TENNISBOT_CONTROL_SETUP、TENNISBOT_LOCAL_SETUP 环境变量覆盖。
  日志目录包含 session.json、left.mp4、right.mp4、frames.ndjson、chassis.ndjson、
  detections.ndjson、observations.ndjson、targets.ndjson 和 events.ndjson。
`);
}
