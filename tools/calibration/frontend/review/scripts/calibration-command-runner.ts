import { resolve, sep } from "node:path";

export type CalibrationCommandPlan = {
  command: string;
  argv: string[];
  cwd: string;
};

export type CalibrationCommandRunResult = {
  status: "passed" | "failed" | "rejected";
  command: string;
  exitCode: number | null;
  durationMs: number;
  stdout: string;
  stderr: string;
  error?: string;
};

type RunnerRoots = {
  repoRoot: string;
  calibrationRoot: string;
};

const defaultCalibrationRoot = resolve(import.meta.dirname, "..", "..", "..");
const defaultRepoRoot = resolve(defaultCalibrationRoot, "..", "..");
const maxCommandLength = 6_000;
const defaultTimeoutMs = 120_000;
const maxOutputLength = 40_000;

const booleanFlags = new Set(["--dry-run", "--prepare-uvc-controls"]);
const valueFlags = new Set([
  "--camera-id",
  "--left-camera-id",
  "--right-camera-id",
  "--device",
  "--left-device",
  "--right-device",
  "--output",
  "--frame-count",
  "--pair-count",
  "--interval-ms",
  "--width",
  "--height",
  "--fourcc",
  "--fps",
  "--session",
  "--output-report",
  "--observations",
  "--left-mono",
  "--right-mono",
  "--min-views",
  "--min-pairs",
  "--max-rms-px",
  "--path",
]);
const pathFlags = new Set([
  "--output",
  "--output-report",
  "--session",
  "--observations",
  "--left-mono",
  "--right-mono",
  "--path",
]);
const deviceFlags = new Set(["--device", "--left-device", "--right-device"]);
const numericFlags = new Set([
  "--frame-count",
  "--pair-count",
  "--interval-ms",
  "--width",
  "--height",
  "--fps",
  "--min-views",
  "--min-pairs",
  "--max-rms-px",
]);

const allowedCommandFlags = new Map<string, Set<string>>([
  [
    "capture mono",
    new Set([
      "--camera-id",
      "--device",
      "--output",
      "--frame-count",
      "--interval-ms",
      "--width",
      "--height",
      "--fourcc",
      "--fps",
      "--prepare-uvc-controls",
      "--dry-run",
    ]),
  ],
  [
    "capture stereo",
    new Set([
      "--left-camera-id",
      "--right-camera-id",
      "--left-device",
      "--right-device",
      "--output",
      "--pair-count",
      "--interval-ms",
      "--width",
      "--height",
      "--fourcc",
      "--fps",
      "--prepare-uvc-controls",
      "--dry-run",
    ]),
  ],
  ["capture inspect", new Set(["--session", "--output-report"])],
  ["capture detect-charuco", new Set(["--session", "--output", "--output-report"])],
  [
    "calibrate mono",
    new Set(["--observations", "--output", "--camera-id", "--min-views", "--max-rms-px"]),
  ],
  [
    "calibrate stereo",
    new Set(["--observations", "--left-mono", "--right-mono", "--output", "--min-pairs", "--max-rms-px"]),
  ],
  ["package verify", new Set(["--path"])],
]);

export function createCalibrationCommandPlan(
  command: string,
  roots: RunnerRoots = { repoRoot: defaultRepoRoot, calibrationRoot: defaultCalibrationRoot },
): CalibrationCommandPlan {
  if (command.length > maxCommandLength) {
    throw new Error(`Command is longer than ${maxCommandLength} characters.`);
  }

  const tokens = tokenizeCommand(command.replaceAll(/\\\s*\n/g, " "));
  if (tokens[0] !== "uv" || tokens[1] !== "run" || tokens[2] !== "tennisbot-calibration") {
    throw new Error("Only 'uv run tennisbot-calibration ...' commands are allowed.");
  }
  if (tokens.length < 5) {
    throw new Error("Command is too short.");
  }

  const commandKey = `${tokens[3]} ${tokens[4]}`;
  const allowedFlags = allowedCommandFlags.get(commandKey);
  if (allowedFlags === undefined) {
    throw new Error(`Calibration command is not allowed: ${commandKey}.`);
  }

  validateFlags(tokens.slice(5), allowedFlags, roots);
  return {
    command: tokens.join(" "),
    argv: tokens,
    cwd: roots.calibrationRoot,
  };
}

export async function runCalibrationCommand(
  command: string,
  options: { timeoutMs?: number; roots?: RunnerRoots } = {},
): Promise<CalibrationCommandRunResult> {
  const started = Date.now();
  let plan: CalibrationCommandPlan;
  try {
    plan = createCalibrationCommandPlan(command, options.roots);
  } catch (error) {
    return {
      status: "rejected",
      command,
      exitCode: null,
      durationMs: Date.now() - started,
      stdout: "",
      stderr: "",
      error: formatUnknownError(error),
    };
  }

  const process = Bun.spawn(plan.argv, {
    cwd: plan.cwd,
    stdout: "pipe",
    stderr: "pipe",
    stdin: "ignore",
  });
  const timeoutMs = options.timeoutMs ?? defaultTimeoutMs;
  let timedOut = false;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<number>((resolveTimeout) => {
    timeoutId = setTimeout(() => {
      timedOut = true;
      process.kill();
      resolveTimeout(-1);
    }, timeoutMs);
  });
  const exitCode = await Promise.race([process.exited, timeout]);
  if (timeoutId !== undefined) {
    clearTimeout(timeoutId);
  }
  const [stdout, stderr] = await Promise.all([
    new Response(process.stdout).text(),
    new Response(process.stderr).text(),
  ]);
  const durationMs = Date.now() - started;

  return {
    status: exitCode === 0 && !timedOut ? "passed" : "failed",
    command: plan.command,
    exitCode,
    durationMs,
    stdout: truncateOutput(stdout),
    stderr: truncateOutput(timedOut ? `${stderr}\nTimed out after ${timeoutMs} ms.` : stderr),
  };
}

function validateFlags(tokens: string[], allowedFlags: Set<string>, roots: RunnerRoots): void {
  for (let index = 0; index < tokens.length; index += 1) {
    const flag = tokens[index];
    if (!flag.startsWith("--")) {
      throw new Error(`Unexpected positional argument: ${flag}.`);
    }
    if (!allowedFlags.has(flag)) {
      throw new Error(`Flag is not allowed for this command: ${flag}.`);
    }
    if (booleanFlags.has(flag)) {
      continue;
    }
    if (!valueFlags.has(flag)) {
      throw new Error(`Unsupported flag: ${flag}.`);
    }
    const value = tokens[index + 1];
    if (value === undefined || value.startsWith("--")) {
      throw new Error(`${flag} requires a value.`);
    }
    validateFlagValue(flag, value, roots);
    index += 1;
  }
}

function validateFlagValue(flag: string, value: string, roots: RunnerRoots): void {
  if (deviceFlags.has(flag) && !/^\/dev\/video\d+$/u.test(value)) {
    throw new Error(`${flag} must be a /dev/videoN device path.`);
  }
  if (numericFlags.has(flag)) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed) || parsed < 0) {
      throw new Error(`${flag} must be a non-negative number.`);
    }
  }
  if (!pathFlags.has(flag)) {
    return;
  }

  const path = resolve(roots.calibrationRoot, value);
  if (flag === "--output-report") {
    assertInside(path, resolve(roots.repoRoot, "docs"), `${flag} must stay inside docs/.`);
    return;
  }
  if (flag === "--output") {
    assertInside(path, resolve(roots.repoRoot, "artifacts"), `${flag} must stay inside artifacts/.`);
    return;
  }
  assertInside(path, resolve(roots.repoRoot, "artifacts"), `${flag} must point inside artifacts/.`);
}

function tokenizeCommand(command: string): string[] {
  const tokens: string[] = [];
  let token = "";
  let quote: '"' | "'" | null = null;
  for (let index = 0; index < command.length; index += 1) {
    const char = command[index];
    if (quote !== null) {
      if (char === quote) {
        quote = null;
      } else if (char === "\\" && quote === '"') {
        index += 1;
        token += command[index] ?? "";
      } else {
        token += char;
      }
      continue;
    }
    if (char === '"' || char === "'") {
      quote = char;
      continue;
    }
    if (/\s/u.test(char)) {
      if (token !== "") {
        tokens.push(token);
        token = "";
      }
      continue;
    }
    token += char;
  }
  if (quote !== null) {
    throw new Error("Unclosed quote in command.");
  }
  if (token !== "") {
    tokens.push(token);
  }
  return tokens;
}

function assertInside(path: string, root: string, message: string): void {
  const resolvedRoot = resolve(root);
  if (path !== resolvedRoot && !path.startsWith(`${resolvedRoot}${sep}`)) {
    throw new Error(message);
  }
}

function truncateOutput(output: string): string {
  if (output.length <= maxOutputLength) return output;
  return `${output.slice(0, maxOutputLength)}\n... output truncated ...`;
}

function formatUnknownError(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}
