export type CameraDeviceConfig = {
  id: "left" | "right";
  label: string;
  devicePath: string;
  resolution: {
    width: number;
    height: number;
  };
  fps: number;
};

export type ArtifactConfig = {
  yoloModelPackagePath: string;
  stereoCalibrationPackagePath: string;
};

export type Live3dMode = "fixture";

export type Live3dConfig = {
  mode: Live3dMode;
  cameras: {
    left: CameraDeviceConfig;
    right: CameraDeviceConfig;
  };
  artifacts: ArtifactConfig;
};

export const defaultLive3dConfig: Live3dConfig = {
  mode: "fixture",
  cameras: {
    left: {
      id: "left",
      label: "Left USB camera",
      devicePath: "/dev/video0",
      resolution: { width: 1280, height: 720 },
      fps: 60,
    },
    right: {
      id: "right",
      label: "Right USB camera",
      devicePath: "/dev/video2",
      resolution: { width: 1280, height: 720 },
      fps: 60,
    },
  },
  artifacts: {
    yoloModelPackagePath: "../../artifacts/models/tennis_ball_yolo",
    stereoCalibrationPackagePath:
      "../../artifacts/calibration/stereo_cam1_cam2",
  },
};

export function describeFixtureMode(mode: Live3dMode): string {
  if (mode === "fixture") {
    return "Fixture mode: static UI data only. This does not validate live cameras, YOLO inference, stereo tracking, triangulation, or prediction.";
  }

  const exhaustive: never = mode;
  return exhaustive;
}
