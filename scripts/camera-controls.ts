export type CameraControl = {
  name: string;
  value: string;
};

export const defaultCameraControls: CameraControl[] = [
  { name: "brightness", value: "-5" },
  { name: "contrast", value: "1" },
  { name: "saturation", value: "64" },
  { name: "white_balance_automatic", value: "0" },
  { name: "white_balance_temperature", value: "4600" },
  { name: "gamma", value: "100" },
  { name: "gain", value: "32" },
  { name: "power_line_frequency", value: "1" },
  { name: "sharpness", value: "1" },
  { name: "backlight_compensation", value: "0" },
  { name: "auto_exposure", value: "1" },
  { name: "exposure_time_absolute", value: "10" },
  { name: "focus_automatic_continuous", value: "0" },
  { name: "focus_absolute", value: "0" },
];

export function applyDefaultCameraControls(devices: readonly [string, string], cwd: string): void {
  for (const command of buildCameraControlCommands(devices)) {
    const result = Bun.spawnSync(command, {
      cwd,
      env: process.env,
      stdout: "inherit",
      stderr: "inherit",
    });
    if (result.exitCode !== 0) {
      throw new Error(`Failed to apply camera controls: ${displayCameraControlCommand(command)}`);
    }
  }
}

export function buildCameraControlCommands(devices: readonly [string, string]): string[][] {
  return devices.flatMap((device) =>
    defaultCameraControls.map((control) => ["v4l2-ctl", "-d", device, `--set-ctrl=${control.name}=${control.value}`]),
  );
}

export function displayCameraControlCommand(command: string[]): string {
  return command.map(shellWord).join(" ");
}

function shellWord(value: string): string {
  return /^[A-Za-z0-9_./:=,@+-]+$/.test(value) ? value : `'${value.replaceAll("'", "'\\''")}'`;
}
