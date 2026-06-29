#!/usr/bin/env bun
import { existsSync, readdirSync, readlinkSync, realpathSync } from "node:fs";
import { basename, dirname, resolve } from "node:path";

type Args = {
  help: boolean;
  json: boolean;
};

type DeviceInfo = {
  device: string;
  card: string;
  bus: string;
  driver: string;
  capabilities: string[];
  byId: string[];
  byPath: string[];
  preferred: string;
};

type DetectionResult = {
  created_at: string;
  devices: DeviceInfo[];
  selected: {
    left?: DeviceInfo;
    right?: DeviceInfo;
  };
  warnings: string[];
};

const args = parseArgs(Bun.argv.slice(2));
if (args.help) {
  printUsage();
  process.exit(0);
}

const result = detectCameraDevices();
if (args.json) {
  console.log(JSON.stringify(result, null, 2));
} else {
  printHuman(result);
}
process.exit(result.devices.length >= 2 ? 0 : 1);

function detectCameraDevices(): DetectionResult {
  const symlinks = readV4lSymlinks();
  const rawDevices = listVideoDevices();
  const devices = rawDevices
    .map((device) => deviceInfo(device, symlinks))
    .filter((device) => isCaptureDevice(device))
    .sort(compareDeviceInfo);
  return {
    created_at: new Date().toISOString(),
    devices,
    selected: {
      left: devices[0],
      right: devices[1],
    },
    warnings: warningsFor(devices),
  };
}

function listVideoDevices(): string[] {
  if (!existsSync("/dev")) return [];
  return readdirSync("/dev")
    .filter((name) => /^video\d+$/u.test(name))
    .map((name) => `/dev/${name}`)
    .sort((left, right) => Number(left.replace("/dev/video", "")) - Number(right.replace("/dev/video", "")));
}

function readV4lSymlinks(): Map<string, { byId: string[]; byPath: string[] }> {
  const result = new Map<string, { byId: string[]; byPath: string[] }>();
  for (const [root, key] of [
    ["/dev/v4l/by-id", "byId"],
    ["/dev/v4l/by-path", "byPath"],
  ] as const) {
    if (!existsSync(root)) continue;
    for (const name of readdirSync(root)) {
      const linkPath = resolve(root, name);
      let target: string;
      try {
        target = realpathSync(resolve(dirname(linkPath), readlinkSync(linkPath)));
      } catch {
        continue;
      }
      const entry = result.get(target) ?? { byId: [], byPath: [] };
      entry[key].push(linkPath);
      result.set(target, entry);
    }
  }
  for (const value of result.values()) {
    value.byId.sort();
    value.byPath.sort();
  }
  return result;
}

function deviceInfo(device: string, symlinks: Map<string, { byId: string[]; byPath: string[] }>): DeviceInfo {
  const detail = run(["v4l2-ctl", "-D", "-d", device]);
  const parsed = parseV4lDetail(detail.stdout);
  const realDevice = safeRealpath(device);
  const links = symlinks.get(realDevice) ?? { byId: [], byPath: [] };
  return {
    device,
    card: parsed.card,
    bus: parsed.bus,
    driver: parsed.driver,
    capabilities: parsed.capabilities,
    byId: links.byId,
    byPath: links.byPath,
    preferred: links.byId[0] ?? links.byPath[0] ?? device,
  };
}

function parseV4lDetail(text: string): Pick<DeviceInfo, "card" | "bus" | "driver" | "capabilities"> {
  const lines = text.split("\n");
  const driver = valueAfterColon(lines.find((line) => line.includes("Driver name"))) ?? "unknown";
  const card = valueAfterColon(lines.find((line) => line.includes("Card type"))) ?? "unknown";
  const bus = valueAfterColon(lines.find((line) => line.includes("Bus info"))) ?? "unknown";
  const capabilities = lines
    .map((line) => line.trim())
    .filter((line) => /^(Video|Metadata|Streaming|Extended|Read\/Write|Device)/u.test(line));
  return { card, bus, driver, capabilities };
}

function valueAfterColon(line: string | undefined): string | undefined {
  if (line === undefined) return undefined;
  const index = line.indexOf(":");
  if (index < 0) return undefined;
  const value = line.slice(index + 1).trim();
  return value === "" ? undefined : value;
}

function isCaptureDevice(device: DeviceInfo): boolean {
  if (device.capabilities.length === 0) return true;
  return device.capabilities.some((item) => item === "Video Capture" || item === "Video Capture Multiplanar");
}

function compareDeviceInfo(left: DeviceInfo, right: DeviceInfo): number {
  const leftKey = `${left.bus} ${left.preferred} ${left.device}`;
  const rightKey = `${right.bus} ${right.preferred} ${right.device}`;
  return leftKey.localeCompare(rightKey, "en");
}

function warningsFor(devices: DeviceInfo[]): string[] {
  const warnings: string[] = [];
  if (devices.length < 2) {
    warnings.push("Fewer than two V4L2 capture devices were detected.");
  }
  const cards = new Set(devices.map((device) => device.card));
  const serialLikeLinks = devices.filter((device) => device.byId.length > 0).length;
  if (devices.length >= 2 && cards.size === 1 && serialLikeLinks < 2) {
    warnings.push(
      "Detected cameras have the same card name and no unique by-id symlink for every device. Left/right identity cannot be proven after USB ports move; verify visually.",
    );
  }
  if (devices.some((device) => device.byId.length === 0)) {
    warnings.push("At least one camera has no /dev/v4l/by-id symlink; falling back to by-path or /dev/videoN.");
  }
  return warnings;
}

function printHuman(result: DetectionResult): void {
  console.log("Detected V4L2 capture devices:");
  if (result.devices.length === 0) {
    console.log("- none");
  }
  for (const [index, device] of result.devices.entries()) {
    console.log(`- ${index}: ${device.preferred}`);
    console.log(`  device: ${device.device}`);
    console.log(`  card: ${device.card}`);
    console.log(`  bus: ${device.bus}`);
    if (device.byId.length > 0) console.log(`  by-id: ${device.byId.join(", ")}`);
    if (device.byPath.length > 0) console.log(`  by-path: ${device.byPath.join(", ")}`);
  }
  if (result.warnings.length > 0) {
    console.log("");
    console.log("Warnings:");
    for (const warning of result.warnings) console.log(`- ${warning}`);
  }
  const left = result.selected.left?.preferred;
  const right = result.selected.right?.preferred;
  if (left === undefined || right === undefined) return;
  console.log("");
  console.log("Suggested command arguments:");
  console.log(`calibration mono left:  --device ${shellQuote(left)}`);
  console.log(`calibration mono right: --device ${shellQuote(right)}`);
  console.log(`calibration stereo:     --left-device ${shellQuote(left)} --right-device ${shellQuote(right)}`);
  console.log(`Live3D hardware UVC:    --uvc-devices ${shellQuote(`${left},${right}`)}`);
  console.log(`legacy stereo-gui:      --left-device ${shellQuote(left)} --right-device ${shellQuote(right)}`);
  console.log("");
  console.log("Use the suggested left/right order as a starting point and verify visually after moving USB ports.");
}

function shellQuote(value: string): string {
  if (/^[A-Za-z0-9_/:.,+=@%-]+$/u.test(value)) return value;
  return `'${value.replaceAll("'", "'\\''")}'`;
}

function safeRealpath(path: string): string {
  try {
    return realpathSync(path);
  } catch {
    return path;
  }
}

function run(command: string[]): { exitCode: number; stdout: string; stderr: string } {
  const result = Bun.spawnSync(command, { stdout: "pipe", stderr: "pipe" });
  return {
    exitCode: result.exitCode,
    stdout: result.stdout.toString(),
    stderr: result.stderr.toString(),
  };
}

function parseArgs(values: string[]): Args {
  const parsed: Args = { help: false, json: false };
  for (const value of values) {
    if (value === "--help" || value === "-h") {
      parsed.help = true;
    } else if (value === "--json") {
      parsed.json = true;
    } else {
      throw new Error(`Unknown argument: ${value}`);
    }
  }
  return parsed;
}

function printUsage(): void {
  console.log(`Usage: bun scripts/detect-camera-devices.ts [--json]

Lists V4L2 capture devices, stable /dev/v4l symlinks when available, and
suggested left/right arguments for TennisBot camera commands.`);
}
