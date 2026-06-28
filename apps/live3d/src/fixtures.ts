import type { Live3dConfig } from "./config";

export type DetectionBox = {
  label: string;
  confidence: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type CameraFixture = {
  name: string;
  frameLabel: string;
  detections: DetectionBox[];
};

export type StatusState = "ready" | "pending" | "blocked" | "fixture";

export type RuntimeStatusItem = {
  label: string;
  state: StatusState;
  detail: string;
};

export type Point3d = {
  x: number;
  y: number;
  z: number;
};

export type SceneFixture = {
  ball: Point3d;
  trail: Point3d[];
  prediction: Point3d[];
  landing: Point3d;
};

export type Live3dFixture = {
  cameras: {
    left: CameraFixture;
    right: CameraFixture;
  };
  scene: SceneFixture;
  status: RuntimeStatusItem[];
};

export function createFixture(config: Live3dConfig): Live3dFixture {
  return {
    cameras: {
      left: {
        name: config.cameras.left.label,
        frameLabel: config.cameras.left.devicePath,
        detections: [
          {
            label: "tennis_ball",
            confidence: 0.91,
            x: 66,
            y: 34,
            width: 8,
            height: 12,
          },
        ],
      },
      right: {
        name: config.cameras.right.label,
        frameLabel: config.cameras.right.devicePath,
        detections: [
          {
            label: "tennis_ball",
            confidence: 0.89,
            x: 58,
            y: 37,
            width: 8,
            height: 12,
          },
        ],
      },
    },
    scene: {
      ball: { x: 0.8, y: 1.4, z: 4.8 },
      trail: [
        { x: -1.2, y: 1.0, z: 7.2 },
        { x: -0.7, y: 1.2, z: 6.3 },
        { x: -0.1, y: 1.35, z: 5.5 },
        { x: 0.8, y: 1.4, z: 4.8 },
      ],
      prediction: [
        { x: 0.8, y: 1.4, z: 4.8 },
        { x: 1.4, y: 1.2, z: 3.9 },
        { x: 1.9, y: 0.9, z: 3.0 },
        { x: 2.3, y: 0.45, z: 2.1 },
      ],
      landing: { x: 2.6, y: 0, z: 1.4 },
    },
    status: [
      {
        label: "Camera",
        state: "fixture",
        detail:
          "Configured placeholders only; live USB stream opening is not implemented in this shell.",
      },
      {
        label: "Model",
        state: "pending",
        detail: `Expected package: ${config.artifacts.yoloModelPackagePath}`,
      },
      {
        label: "Calibration",
        state: "pending",
        detail: `Expected package: ${config.artifacts.stereoCalibrationPackagePath}`,
      },
      {
        label: "Tracking",
        state: "fixture",
        detail:
          "Static paired detections are rendered for UI layout only; no real tracking validation.",
      },
      {
        label: "Prediction",
        state: "fixture",
        detail:
          "Static 3D curve placeholder only; no trajectory or landing validation.",
      },
    ],
  };
}
