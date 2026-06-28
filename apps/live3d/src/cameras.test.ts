import { describe, expect, test } from "bun:test";
import { defaultLive3dConfig, type Live3dConfig } from "./config";
import {
  attachCameraStream,
  startStereoCameraRuntime,
  type MediaDevicesRuntime,
  type VideoStreamElement,
} from "./cameras";

describe("Live3D browser camera runtime", () => {
  test("media API unsupported returns blocked status", async () => {
    const status = await startStereoCameraRuntime(undefined, defaultLive3dConfig);

    expect(status.state).toBe("blocked");
    expect(status.left.code).toBe("unsupported-media-api");
    expect(status.right.code).toBe("unsupported-media-api");
  });

  test("one available camera returns blocked status for stereo runtime", async () => {
    const mediaDevices = fakeMediaDevices({
      devices: [videoDevice("only-camera", "USB Camera")],
    });

    const status = await startStereoCameraRuntime(mediaDevices, defaultLive3dConfig);

    expect(status.state).toBe("blocked");
    expect(status.left.code).toBe("missing-camera");
    expect(status.right.code).toBe("missing-camera");
    expect(mediaDevices.calls).toHaveLength(0);
  });

  test("two available cameras request two streams with expected constraints", async () => {
    const mediaDevices = fakeMediaDevices({
      devices: [
        videoDevice("device-left", "Court Left USB"),
        videoDevice("device-right", "Court Right USB"),
      ],
    });

    const status = await startStereoCameraRuntime(mediaDevices, defaultLive3dConfig);

    expect(status.state).toBe("ready");
    expect(mediaDevices.calls).toEqual([
      {
        audio: false,
        video: {
          deviceId: { exact: "device-left" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 60 },
        },
      },
      {
        audio: false,
        video: {
          deviceId: { exact: "device-right" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 60 },
        },
      },
    ]);
    expect(status.left.code).toBe("opened");
    expect(status.right.code).toBe("opened");
  });

  test("deviceId config takes precedence over label match", async () => {
    const config: Live3dConfig = {
      ...defaultLive3dConfig,
      cameras: {
        left: {
          ...defaultLive3dConfig.cameras.left,
          deviceId: "exact-left",
          labelMatch: "unmatched",
        },
        right: {
          ...defaultLive3dConfig.cameras.right,
          deviceId: "exact-right",
          labelMatch: "unmatched",
        },
      },
    };
    const mediaDevices = fakeMediaDevices({
      devices: [
        videoDevice("exact-left", "Camera A"),
        videoDevice("exact-right", "Camera B"),
      ],
    });

    const status = await startStereoCameraRuntime(mediaDevices, config);

    expect(status.state).toBe("ready");
    expect(mediaDevices.calls[0]?.video).toMatchObject({
      deviceId: { exact: "exact-left" },
    });
    expect(mediaDevices.calls[1]?.video).toMatchObject({
      deviceId: { exact: "exact-right" },
    });
  });

  test("permission or getUserMedia failure returns blocked status", async () => {
    const mediaDevices = fakeMediaDevices({
      devices: [
        videoDevice("device-left", "Court Left USB"),
        videoDevice("device-right", "Court Right USB"),
      ],
      failure: new DOMException("permission blocked", "NotAllowedError"),
    });

    const status = await startStereoCameraRuntime(mediaDevices, defaultLive3dConfig);

    expect(status.state).toBe("blocked");
    expect(status.left.code).toBe("permission-denied");
    expect(status.right.code).toBe("permission-denied");
  });

  test("attachCameraStream sets video element playback fields", () => {
    const stream = fakeStream("attached-stream");
    const video: VideoStreamElement = {
      srcObject: null,
      muted: false,
      autoplay: false,
      playsInline: false,
      play: async () => undefined,
    };

    attachCameraStream(video, stream);

    expect(video.srcObject).toBe(stream);
    expect(video.muted).toBe(true);
    expect(video.autoplay).toBe(true);
    expect(video.playsInline).toBe(true);
  });
});

function fakeMediaDevices(options: {
  devices: MediaDeviceInfo[];
  failure?: Error;
}): MediaDevicesRuntime & { calls: MediaStreamConstraints[] } {
  const calls: MediaStreamConstraints[] = [];
  return {
    calls,
    enumerateDevices: async () => options.devices,
    getUserMedia: async (constraints) => {
      calls.push(constraints);
      if (options.failure !== undefined) {
        throw options.failure;
      }
      return fakeStream(`stream-${calls.length}`);
    },
  };
}

function videoDevice(deviceId: string, label: string): MediaDeviceInfo {
  return {
    deviceId,
    groupId: "group",
    kind: "videoinput",
    label,
    toJSON: () => ({ deviceId, groupId: "group", kind: "videoinput", label }),
  } as MediaDeviceInfo;
}

function fakeStream(id: string): MediaStream {
  return {
    id,
    getTracks: () => [],
  } as unknown as MediaStream;
}
