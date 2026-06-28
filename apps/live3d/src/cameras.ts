import type { CameraDeviceConfig, Live3dConfig } from "./config";

export type CameraSide = "left" | "right";

export type CameraRuntimeStatusCode =
  | "not-started"
  | "starting"
  | "opened"
  | "unsupported-media-api"
  | "missing-camera"
  | "permission-denied"
  | "get-user-media-failed";

export type CameraRuntimeStatus = {
  side: CameraSide;
  state: "ready" | "pending" | "blocked";
  code: CameraRuntimeStatusCode;
  label: string;
  detail: string;
  deviceId?: string;
  deviceLabel?: string;
};

export type StereoCameraRuntimeStatus =
  | {
      state: "ready";
      left: CameraRuntimeStatus;
      right: CameraRuntimeStatus;
      streams: StereoCameraStreams;
      devices: CameraRuntimeDevice[];
    }
  | {
      state: "pending";
      left: CameraRuntimeStatus;
      right: CameraRuntimeStatus;
      devices: CameraRuntimeDevice[];
    }
  | {
      state: "blocked";
      left: CameraRuntimeStatus;
      right: CameraRuntimeStatus;
      devices: CameraRuntimeDevice[];
    };

export type StereoCameraStreams = {
  left: MediaStream;
  right: MediaStream;
};

export type CameraRuntimeDevice = {
  deviceId: string;
  label: string;
  kind: "videoinput";
};

export type MediaDevicesRuntime = {
  enumerateDevices?: () => Promise<MediaDeviceInfo[]>;
  getUserMedia?: (constraints: MediaStreamConstraints) => Promise<MediaStream>;
};

export type VideoStreamElement = {
  srcObject: MediaProvider | null;
  muted: boolean;
  autoplay: boolean;
  playsInline: boolean;
  play?: () => Promise<unknown>;
};

type SelectedCameraDevices = {
  left: CameraRuntimeDevice;
  right: CameraRuntimeDevice;
};

export function createStereoCameraIdleStatus(config: Live3dConfig): StereoCameraRuntimeStatus {
  return pendingPair(
    "not-started",
    "Camera streams have not been opened. Start cameras when two USB devices are connected and browser permission can be granted.",
    config,
  );
}

export function createStereoCameraStartingStatus(
  config: Live3dConfig,
): StereoCameraRuntimeStatus {
  return pendingPair(
    "starting",
    "Opening browser camera streams and waiting for permission if required.",
    config,
  );
}

export async function startStereoCameraRuntime(
  mediaDevices: MediaDevicesRuntime | undefined,
  config: Live3dConfig,
): Promise<StereoCameraRuntimeStatus> {
  if (
    mediaDevices?.enumerateDevices === undefined ||
    mediaDevices.getUserMedia === undefined
  ) {
    return blockedPair(
      "unsupported-media-api",
      "Browser mediaDevices APIs are unavailable. Live USB camera input is blocked, but fixture placeholders can still render.",
    );
  }

  let devices: CameraRuntimeDevice[];
  try {
    const enumeratedDevices = await mediaDevices.enumerateDevices();
    devices = enumeratedDevices
      .filter((device): device is MediaDeviceInfo & { kind: "videoinput" } => device.kind === "videoinput")
      .map((device) => ({
        deviceId: device.deviceId,
        label: device.label,
        kind: "videoinput",
      }));
  } catch (error) {
    return blockedPair(
      "unsupported-media-api",
      `Camera device enumeration failed: ${formatUnknownError(error)}`,
    );
  }

  const selected = selectStereoCameraDevices(devices, config);
  if (selected === null) {
    const detail =
      devices.length === 1
        ? "Only one video input is available. Live3D stereo runtime requires two camera devices."
        : "Fewer than two video inputs are available. Live3D stereo runtime requires two camera devices.";
    return blockedPair("missing-camera", detail, devices);
  }

  let leftStream: MediaStream | undefined;
  try {
    leftStream = await mediaDevices.getUserMedia(
      createCameraConstraints(config.cameras.left, selected.left),
    );
    const rightStream = await mediaDevices.getUserMedia(
      createCameraConstraints(config.cameras.right, selected.right),
    );

    return {
      state: "ready",
      left: openedStatus("left", config.cameras.left, selected.left),
      right: openedStatus("right", config.cameras.right, selected.right),
      streams: { left: leftStream, right: rightStream },
      devices,
    };
  } catch (error) {
    stopStream(leftStream);
    const code = isPermissionDenied(error)
      ? "permission-denied"
      : "get-user-media-failed";
    const detail =
      code === "permission-denied"
        ? `Camera permission was denied: ${formatUnknownError(error)}`
        : `Camera stream startup failed: ${formatUnknownError(error)}`;
    return blockedPair(code, detail, devices);
  }
}

export function selectStereoCameraDevices(
  devices: CameraRuntimeDevice[],
  config: Live3dConfig,
): SelectedCameraDevices | null {
  if (devices.length < 2) {
    return null;
  }

  const left = selectCameraDevice(devices, config.cameras.left, []);
  if (left === null) {
    return null;
  }

  const right = selectCameraDevice(devices, config.cameras.right, [left.deviceId]);
  if (right === null) {
    return null;
  }

  return { left, right };
}

export function createCameraConstraints(
  camera: CameraDeviceConfig,
  device: CameraRuntimeDevice,
): MediaStreamConstraints {
  return {
    audio: false,
    video: {
      deviceId: { exact: device.deviceId },
      width: { ideal: camera.resolution.width },
      height: { ideal: camera.resolution.height },
      frameRate: { ideal: camera.fps },
    },
  };
}

export function attachCameraStream(video: VideoStreamElement, stream: MediaStream): void {
  video.srcObject = stream;
  video.muted = true;
  video.autoplay = true;
  video.playsInline = true;
  void video.play?.().catch(() => undefined);
}

export function stopStereoCameraRuntime(status: StereoCameraRuntimeStatus): void {
  if (status.state !== "ready") {
    return;
  }

  stopStream(status.streams.left);
  stopStream(status.streams.right);
}

function selectCameraDevice(
  devices: CameraRuntimeDevice[],
  camera: CameraDeviceConfig,
  excludedDeviceIds: string[],
): CameraRuntimeDevice | null {
  const availableDevices = devices.filter(
    (device) => !excludedDeviceIds.includes(device.deviceId),
  );

  if (camera.deviceId !== undefined) {
    const byDeviceId = availableDevices.find((device) => device.deviceId === camera.deviceId);
    if (byDeviceId !== undefined) {
      return byDeviceId;
    }
  }

  if (camera.labelMatch !== undefined && camera.labelMatch.trim() !== "") {
    const labelNeedle = camera.labelMatch.toLowerCase();
    const byLabel = availableDevices.find((device) =>
      device.label.toLowerCase().includes(labelNeedle),
    );
    if (byLabel !== undefined) {
      return byLabel;
    }
  }

  return availableDevices[0] ?? null;
}

function openedStatus(
  side: CameraSide,
  config: CameraDeviceConfig,
  device: CameraRuntimeDevice,
): CameraRuntimeStatus {
  return {
    side,
    state: "ready",
    code: "opened",
    label: `${config.label} opened`,
    detail: `${config.resolution.width}x${config.resolution.height} @ ${config.fps} fps requested from browser device ${device.label || device.deviceId}.`,
    deviceId: device.deviceId,
    deviceLabel: device.label,
  };
}

function pendingPair(
  code: Extract<CameraRuntimeStatusCode, "not-started" | "starting">,
  detail: string,
  config: Live3dConfig,
): StereoCameraRuntimeStatus {
  return {
    state: "pending",
    left: pendingStatus("left", code, detail, config.cameras.left),
    right: pendingStatus("right", code, detail, config.cameras.right),
    devices: [],
  };
}

function pendingStatus(
  side: CameraSide,
  code: Extract<CameraRuntimeStatusCode, "not-started" | "starting">,
  detail: string,
  config: CameraDeviceConfig,
): CameraRuntimeStatus {
  return {
    side,
    state: "pending",
    code,
    label: code === "starting" ? `${config.label} starting` : `${config.label} idle`,
    detail,
  };
}

function blockedPair(
  code: Exclude<CameraRuntimeStatusCode, "opened" | "not-started" | "starting">,
  detail: string,
  devices: CameraRuntimeDevice[] = [],
): StereoCameraRuntimeStatus {
  return {
    state: "blocked",
    left: blockedStatus("left", code, detail),
    right: blockedStatus("right", code, detail),
    devices,
  };
}

function blockedStatus(
  side: CameraSide,
  code: Exclude<CameraRuntimeStatusCode, "opened" | "not-started" | "starting">,
  detail: string,
): CameraRuntimeStatus {
  return {
    side,
    state: "blocked",
    code,
    label: `${side} camera blocked`,
    detail,
  };
}

function stopStream(stream: MediaStream | undefined): void {
  stream?.getTracks().forEach((track) => track.stop());
}

function isPermissionDenied(error: unknown): boolean {
  return (
    error instanceof DOMException &&
    (error.name === "NotAllowedError" || error.name === "SecurityError")
  );
}

function formatUnknownError(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
