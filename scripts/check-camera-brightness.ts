#!/usr/bin/env bun
import { existsSync, readdirSync } from "node:fs";

type Args = {
  help: boolean;
  json: boolean;
  devices?: string[];
  width: number;
  height: number;
  fps: number;
  inputFormat: string;
  timeoutMs: number;
};

type DeviceResult = {
  device: string;
  card: string;
  bus: string;
  average_brightness: number | null;
  sample_bytes: number;
  status: "ok" | "failed";
  error?: string;
};

type BrightnessReport = {
  created_at: string;
  devices: DeviceResult[];
  darkest_device: string | null;
  command_hints: string[];
};

const args = parseArgs(Bun.argv.slice(2));
if (args.help) {
  printUsage();
  process.exit(0);
}

const report = await checkBrightness(args);
if (args.json) {
  console.log(JSON.stringify(report, null, 2));
} else {
  printHuman(report);
}
process.exit(report.devices.filter((device) => device.status === "ok").length >= 2 ? 0 : 1);

async function checkBrightness(args: Args): Promise<BrightnessReport> {
  const selectedDevices = args.devices ?? listCaptureDevices().slice(0, 2).map((device) => device.device);
  const devices: DeviceResult[] = [];
  for (const device of selectedDevices.slice(0, 2)) {
    devices.push(await measureDevice(device, args));
  }
  const okDevices = devices.filter((device) => device.average_brightness !== null);
  const darkest = [...okDevices].sort((left, right) => left.average_brightness! - right.average_brightness!)[0];
  return {
    created_at: new Date().toISOString(),
    devices,
    darkest_device: darkest?.device ?? null,
    command_hints: commandHints(devices),
  };
}

function listCaptureDevices(): Array<{ device: string; card: string; bus: string }> {
  if (!existsSync("/dev")) return [];
  return readdirSync("/dev")
    .filter((name) => /^video\d+$/u.test(name))
    .map((name) => `/dev/${name}`)
    .map((device) => ({ device, ...readDeviceInfo(device) }))
    .filter((device) => deviceHasCaptureCapability(device.device) && isUsbBus(device.bus))
    .sort((left, right) => Number(left.device.replace("/dev/video", "")) - Number(right.device.replace("/dev/video", "")));
}

async function measureDevice(device: string, args: Args): Promise<DeviceResult> {
  const info = readDeviceInfo(device);
  const attempts = args.inputFormat === "" ? [""] : [args.inputFormat, ""];
  let lastError = "capture failed";
  for (const inputFormat of attempts) {
    const result = await captureGrayFrame(device, { ...args, inputFormat });
    if (result.ok) {
      return {
        device,
        card: info.card,
        bus: info.bus,
        average_brightness: result.average,
        sample_bytes: result.bytes,
        status: "ok",
      };
    }
    lastError = result.error;
  }
  return {
    device,
    card: info.card,
    bus: info.bus,
    average_brightness: null,
    sample_bytes: 0,
    status: "failed",
    error: lastError,
  };
}

async function captureGrayFrame(
  device: string,
  args: Args,
): Promise<{ ok: true; average: number; bytes: number } | { ok: false; error: string }> {
  const command = [
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "error",
    "-f",
    "v4l2",
    ...(args.inputFormat === "" ? [] : ["-input_format", args.inputFormat]),
    "-video_size",
    `${args.width}x${args.height}`,
    "-framerate",
    String(args.fps),
    "-i",
    device,
    "-frames:v",
    "1",
    "-f",
    "rawvideo",
    "-pix_fmt",
    "gray",
    "-",
  ];
  const result = await runWithTimeout(command, args.timeoutMs);
  if (result.timedOut) {
    return { ok: false, error: `ffmpeg timed out after ${args.timeoutMs} ms` };
  }
  if (result.exitCode !== 0) {
    return { ok: false, error: result.stderr.trim() || `ffmpeg exited ${result.exitCode}` };
  }
  if (result.stdout.length === 0) {
    return { ok: false, error: "ffmpeg produced no frame bytes" };
  }
  let sum = 0;
  for (const value of result.stdout) sum += value;
  return {
    ok: true,
    average: Number((sum / result.stdout.length).toFixed(2)),
    bytes: result.stdout.length,
  };
}

async function runWithTimeout(
  command: string[],
  timeoutMs: number,
): Promise<{ exitCode: number; stdout: Uint8Array; stderr: string; timedOut: boolean }> {
  const child = Bun.spawn(command, {
    stdin: "ignore",
    stdout: "pipe",
    stderr: "pipe",
  });
  let timedOut = false;
  const timeout = setTimeout(() => {
    timedOut = true;
    child.kill();
  }, timeoutMs);
  try {
    const [stdoutBuffer, stderrText, exitCode] = await Promise.all([
      new Response(child.stdout).arrayBuffer(),
      new Response(child.stderr).text(),
      child.exited,
    ]);
    return {
      exitCode,
      stdout: new Uint8Array(stdoutBuffer),
      stderr: stderrText,
      timedOut,
    };
  } finally {
    clearTimeout(timeout);
  }
}

function readDeviceInfo(device: string): { card: string; bus: string } {
  const result = Bun.spawnSync(["v4l2-ctl", "-D", "-d", device], { stdout: "pipe", stderr: "ignore" });
  const text = result.stdout.toString();
  return {
    card: valueAfterColon(text, "Card type") ?? "unknown",
    bus: valueAfterColon(text, "Bus info") ?? "unknown",
  };
}

function deviceHasCaptureCapability(device: string): boolean {
  const result = Bun.spawnSync(["v4l2-ctl", "-D", "-d", device], { stdout: "pipe", stderr: "ignore" });
  if (result.exitCode !== 0) return false;
  const text = result.stdout.toString();
  return text.includes("Video Capture");
}

function isUsbBus(bus: string): boolean {
  return bus.toLowerCase().includes("usb");
}

function valueAfterColon(text: string, label: string): string | undefined {
  const line = text.split("\n").find((item) => item.includes(label));
  if (line === undefined) return undefined;
  const index = line.indexOf(":");
  if (index < 0) return undefined;
  const value = line.slice(index + 1).trim();
  return value === "" ? undefined : value;
}

function commandHints(devices: DeviceResult[]): string[] {
  const ok = devices.filter((device) => device.status === "ok");
  if (ok.length < 2) return [];
  const [left, right] = ok;
  return [
    `calibration stereo: --left-device ${left.device} --right-device ${right.device}`,
    `Live3D UVC: --uvc-devices ${left.device},${right.device}`,
    `legacy stereo-gui: --left-device ${left.device} --right-device ${right.device}`,
  ];
}

function printHuman(report: BrightnessReport): void {
  console.log("Camera brightness check:");
  if (report.devices.length === 0) {
    console.log("- no V4L2 capture devices found");
    return;
  }
  for (const device of report.devices) {
    const value = device.average_brightness === null ? "failed" : `${device.average_brightness.toFixed(2)} / 255`;
    console.log(`- ${device.device}: ${value}`);
    console.log(`  card: ${device.card}`);
    console.log(`  bus: ${device.bus}`);
    if (device.error !== undefined) console.log(`  error: ${device.error}`);
  }
  if (report.darkest_device !== null) {
    console.log("");
    console.log(`Darkest camera candidate: ${report.darkest_device}`);
    console.log("If one lens cap is still on, it is probably the device with the lower average brightness.");
  }
  if (report.command_hints.length > 0) {
    console.log("");
    console.log("Command hints using the measured order:");
    for (const hint of report.command_hints) console.log(`- ${hint}`);
  }
}

function parseArgs(values: string[]): Args {
  const parsed: Args = {
    help: false,
    json: false,
    width: 1280,
    height: 720,
    fps: 30,
    inputFormat: "mjpeg",
    timeoutMs: 5000,
  };
  for (let index = 0; index < values.length; index += 1) {
    const value = values[index];
    if (value === "--help" || value === "-h") {
      parsed.help = true;
    } else if (value === "--json") {
      parsed.json = true;
    } else if (value === "--devices") {
      parsed.devices = requireValue(values, ++index, value)
        .split(",")
        .map((item) => item.trim())
        .filter((item) => item !== "");
    } else if (value === "--width") {
      parsed.width = parsePositiveInteger(value, requireValue(values, ++index, value));
    } else if (value === "--height") {
      parsed.height = parsePositiveInteger(value, requireValue(values, ++index, value));
    } else if (value === "--fps") {
      parsed.fps = parsePositiveInteger(value, requireValue(values, ++index, value));
    } else if (value === "--input-format") {
      parsed.inputFormat = requireValue(values, ++index, value);
    } else if (value === "--timeout-ms") {
      parsed.timeoutMs = parsePositiveInteger(value, requireValue(values, ++index, value));
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  if (parsed.devices !== undefined && parsed.devices.length !== 2) {
    throw new Error("--devices must contain exactly two comma-separated device paths.");
  }
  return parsed;
}

function requireValue(values: string[], index: number, flag: string): string {
  const value = values[index];
  if (value === undefined || value.startsWith("--")) {
    throw new Error(`${flag} requires a value.`);
  }
  return value;
}

function parsePositiveInteger(flag: string, value: string): number {
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed <= 0) {
    throw new Error(`${flag} must be a positive integer.`);
  }
  return parsed;
}

function printUsage(): void {
  console.log(`Usage: bun scripts/check-camera-brightness.ts [options]

Captures one grayscale frame from two USB V4L2 cameras and prints average
brightness. A covered lens should have a much lower average brightness.

Options:
  --devices <left,right>      Comma-separated devices. Default: first two USB V4L2 capture devices.
  --width <px>                Capture width. Default: 1280
  --height <px>               Capture height. Default: 720
  --fps <fps>                 Capture FPS request. Default: 30
  --input-format <format>     V4L2 input format. Default: mjpeg; fallback without format is automatic.
  --timeout-ms <ms>           Per-device capture timeout. Default: 5000
  --json                      Print machine-readable JSON.
`);
}
