#!/usr/bin/env bun

import { resolve } from "node:path";

type Options = {
  topic: string;
  expectedType: string;
  timeoutMs: number;
  hzSeconds: number;
  autoSource: boolean;
  setupFiles: string[];
};

type CommandResult = {
  code: number | null;
  stdout: string;
  stderr: string;
  timedOut: boolean;
};

type ParsedMessage = {
  publishStampSec?: number;
  publishStampNanosec?: number;
  sequenceId?: number;
  x?: number;
  y?: number;
  yaw?: number;
};

const repoRoot = resolve(import.meta.dirname, "..");
const argv = Bun.argv.slice(2);

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
  console.log(`检查: ${options.topic}`);

  const topicList = await runRosCommand(["topic", "list", "-t"], options.timeoutMs, options);
  if (topicList.timedOut) {
    console.log(`topic列表: 超时 ${formatSeconds(options.timeoutMs)}`);
    console.log("结果: FAIL");
    return 1;
  }
  if (topicList.code !== 0) {
    console.log("topic列表: 失败");
    printCommandError(topicList);
    console.log("结果: FAIL");
    return 1;
  }

  const topicType = parseTopicType(topicList.stdout, options.topic);
  if (topicType === undefined) {
    console.log("topic: 不存在");
    console.log(`期望类型: ${options.expectedType}`);
    console.log("结果: FAIL");
    return 1;
  }

  console.log("topic: 存在");
  console.log(`type: ${topicType}`);
  if (topicType !== options.expectedType) {
    console.log(`期望类型: ${options.expectedType}`);
    console.log("结果: FAIL");
    return 1;
  }

  const echo = await runRosCommand(["topic", "echo", "--once", options.topic], options.timeoutMs, options);
  if (echo.timedOut) {
    console.log(`消息: ${formatSeconds(options.timeoutMs)} 内未收到`);
    console.log("结果: FAIL");
    return 1;
  }
  if (echo.code !== 0) {
    console.log("消息: 读取失败");
    printCommandError(echo);
    console.log("结果: FAIL");
    return 1;
  }

  const message = parseChassisPosition(echo.stdout);
  console.log("消息: 收到");
  printParsedMessage(message);

  const errors = validateMessage(message);
  if (options.hzSeconds > 0) {
    await printTopicHz(options);
  }

  if (errors.length > 0) {
    console.log(`字段检查: ${errors.join(", ")}`);
    console.log("结果: FAIL");
    return 1;
  }

  console.log("字段检查: OK");
  console.log("结果: OK");
  return 0;
}

async function printTopicHz(options: Options): Promise<void> {
  const timeoutMs = Math.max(1000, Math.round(options.hzSeconds * 1000));
  const hz = await runRosCommand(["topic", "hz", options.topic], timeoutMs, options, "SIGINT");
  const average = parseLastNumber(hz.stdout, /average rate:\s*([0-9.]+)/g);
  const window = parseLastNumber(hz.stdout, /window:\s*([0-9]+)/g);
  if (average === undefined) {
    console.log(`频率: 未测到 (${formatSeconds(timeoutMs)} 采样)`);
    return;
  }
  const suffix = window === undefined ? "" : `, window ${Math.round(window)}`;
  console.log(`频率: ${average.toFixed(3)} Hz (${formatSeconds(timeoutMs)} 采样${suffix})`);
}

function parseOptions(args: string[]): Options {
  const options: Options = {
    topic: "/robot/chassis_position",
    expectedType: "target_msgs/msg/ChassisPosition",
    timeoutMs: 5000,
    hzSeconds: 4,
    autoSource: true,
    setupFiles: defaultSetupFiles(),
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--help" || arg === "-h") {
      printUsage();
      process.exit(0);
    } else if (arg === "--topic") {
      options.topic = takeValue(args, ++index, arg);
    } else if (arg === "--expected-type") {
      options.expectedType = takeValue(args, ++index, arg);
    } else if (arg === "--timeout") {
      options.timeoutMs = secondsToMs(takeValue(args, ++index, arg), arg);
    } else if (arg === "--hz-seconds") {
      options.hzSeconds = nonnegativeSeconds(takeValue(args, ++index, arg), arg);
    } else if (arg === "--no-hz") {
      options.hzSeconds = 0;
    } else if (arg === "--auto-source") {
      options.autoSource = true;
    } else if (arg === "--no-auto-source") {
      options.autoSource = false;
    } else if (arg === "--clear-setup-files") {
      options.setupFiles = [];
    } else if (arg === "--setup-file") {
      options.setupFiles.push(takeValue(args, ++index, arg));
    } else {
      throw new Error(`Unknown option: ${arg}`);
    }
  }

  if (!options.topic.startsWith("/")) {
    throw new Error("--topic must be an absolute ROS topic name");
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

async function runRosCommand(
  args: string[],
  timeoutMs: number,
  options: Options,
  timeoutSignal: "SIGTERM" | "SIGINT" = "SIGTERM",
): Promise<CommandResult> {
  const command = wrapRosCommand(["ros2", ...args], options);
  let proc: ReturnType<typeof Bun.spawn>;
  try {
    proc = Bun.spawn(command, {
      cwd: repoRoot,
      env: process.env,
      stdin: "ignore",
      stdout: "pipe",
      stderr: "pipe",
    });
  } catch (error) {
    return {
      code: 127,
      stdout: "",
      stderr: error instanceof Error ? error.message : String(error),
      timedOut: false,
    };
  }

  let timedOut = false;
  let hardKillTimer: ReturnType<typeof setTimeout> | undefined;
  const timer = setTimeout(() => {
    timedOut = true;
    proc.kill(timeoutSignal);
    hardKillTimer = setTimeout(() => proc.kill("SIGKILL"), 1000);
  }, timeoutMs);

  try {
    const [code, stdout, stderr] = await Promise.all([
      proc.exited,
      new Response(proc.stdout).text(),
      new Response(proc.stderr).text(),
    ]);
    return { code, stdout, stderr, timedOut };
  } finally {
    clearTimeout(timer);
    if (hardKillTimer !== undefined) clearTimeout(hardKillTimer);
  }
}

function wrapRosCommand(command: string[], options: Options): string[] {
  if (!options.autoSource) return command;
  const sourcePrefix = options.setupFiles
    .filter((item) => item.trim().length > 0)
    .map((item) => `source ${shellQuote(item)} && `)
    .join("");
  return ["bash", "-lc", `${sourcePrefix}exec ${command.map(shellQuote).join(" ")}`];
}

function parseTopicType(output: string, topic: string): string | undefined {
  for (const line of output.split(/\r?\n/)) {
    const match = line.trim().match(/^(.+?)\s+\[(.+)]$/);
    if (match !== null && match[1] === topic) {
      return match[2];
    }
  }
  return undefined;
}

function parseChassisPosition(output: string): ParsedMessage {
  const result: ParsedMessage = {};
  let section = "";
  for (const rawLine of output.split(/\r?\n/)) {
    const line = rawLine.trimEnd();
    const rootMatch = line.match(/^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/);
    if (rootMatch !== null) {
      section = rootMatch[1];
      const value = rootMatch[2].trim();
      if (section === "sequence_id") result.sequenceId = parseFiniteNumber(value);
      else if (section === "x") result.x = parseFiniteNumber(value);
      else if (section === "y") result.y = parseFiniteNumber(value);
      else if (section === "yaw") result.yaw = parseFiniteNumber(value);
      continue;
    }

    if (section === "publish_stamp") {
      const childMatch = line.match(/^\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$/);
      if (childMatch === null) continue;
      const value = parseFiniteNumber(childMatch[2].trim());
      if (childMatch[1] === "sec") result.publishStampSec = value;
      else if (childMatch[1] === "nanosec") result.publishStampNanosec = value;
    }
  }
  return result;
}

function printParsedMessage(message: ParsedMessage): void {
  console.log(`publish_stamp.sec: ${formatValue(message.publishStampSec)}`);
  console.log(`publish_stamp.nanosec: ${formatValue(message.publishStampNanosec)}`);
  console.log(`sequence_id: ${formatValue(message.sequenceId)}`);
  console.log(`x: ${formatValue(message.x)}`);
  console.log(`y: ${formatValue(message.y)}`);
  console.log(`yaw: ${formatValue(message.yaw)}`);
}

function validateMessage(message: ParsedMessage): string[] {
  const errors: string[] = [];
  if (!Number.isFinite(message.publishStampSec)) errors.push("publish_stamp.sec 缺失或非法");
  if (!Number.isFinite(message.publishStampNanosec)) errors.push("publish_stamp.nanosec 缺失或非法");
  if (!Number.isFinite(message.sequenceId)) errors.push("sequence_id 缺失或非法");
  if (!Number.isFinite(message.x)) errors.push("x 缺失或非法");
  if (!Number.isFinite(message.y)) errors.push("y 缺失或非法");
  if (!Number.isFinite(message.yaw)) errors.push("yaw 缺失或非法");
  return errors;
}

function parseLastNumber(output: string, pattern: RegExp): number | undefined {
  let value: number | undefined;
  for (const match of output.matchAll(pattern)) {
    value = Number(match[1]);
  }
  return Number.isFinite(value) ? value : undefined;
}

function parseFiniteNumber(value: string): number | undefined {
  const number = Number(value);
  return Number.isFinite(number) ? number : undefined;
}

function printCommandError(result: CommandResult): void {
  const stderr = result.stderr.trim();
  const stdout = result.stdout.trim();
  if (stderr.length > 0) console.log(`stderr: ${stderr}`);
  else if (stdout.length > 0) console.log(`stdout: ${stdout}`);
}

function secondsToMs(value: string, option: string): number {
  const seconds = nonnegativeSeconds(value, option);
  if (seconds <= 0) throw new Error(`${option} must be greater than 0`);
  return Math.round(seconds * 1000);
}

function nonnegativeSeconds(value: string, option: string): number {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) {
    throw new Error(`${option} must be a nonnegative number of seconds`);
  }
  return seconds;
}

function takeValue(args: string[], index: number, option: string): string {
  const value = args[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${option} requires a value`);
  }
  return value;
}

function formatSeconds(timeoutMs: number): string {
  return `${(timeoutMs / 1000).toFixed(timeoutMs % 1000 === 0 ? 0 : 1)}s`;
}

function formatValue(value: number | undefined): string {
  return value === undefined ? "缺失" : String(value);
}

function shellQuote(value: string): string {
  return /^[A-Za-z0-9_./:=,-]+$/.test(value) ? value : `'${value.replace(/'/g, "'\\''")}'`;
}

function printUsage(): void {
  console.log(`用法:
  bun scripts/check-chassis-position.ts [options]

说明:
  检查 /robot/chassis_position 是否存在、类型是否正确、是否能收到一条消息，并输出关键字段。
  输出是普通文本，不生成 Markdown 文件。

常用:
  bun scripts/check-chassis-position.ts
  bun scripts/check-chassis-position.ts --timeout 8 --hz-seconds 5
  bun scripts/check-chassis-position.ts --no-hz

选项:
  --topic <name>             默认 /robot/chassis_position
  --expected-type <type>     默认 target_msgs/msg/ChassisPosition
  --timeout <seconds>        topic list 和 echo 的超时时间，默认 5
  --hz-seconds <seconds>     频率采样时间，默认 4
  --no-hz                    不采样频率
  --auto-source              自动 source ROS/control/local setup，默认开启
  --no-auto-source           不自动 source
  --setup-file <path>        追加 setup.bash，可重复
  --clear-setup-files        清空默认 setup 列表，配合 --setup-file 使用
`);
}
