import { describe, expect, test } from "bun:test";

import {
  buildCaptureCommand,
  buildDetectCommand,
  buildInspectCommand,
  buildSolveCommand,
  classifyArtifact,
  frameRows,
  observationRows,
  summarizeWorkflow,
  type ImportedArtifact,
} from "./calibration-workspace";

describe("calibration review workspace", () => {
  test("classifies calibration JSON artifacts", () => {
    expect(classifyArtifact({ schema_version: "calibration.capture_session.v1" })).toBe("captureManifest");
    expect(classifyArtifact({ schema_version: "calibration.capture_inspection.v1" })).toBe("captureInspection");
    expect(classifyArtifact({ schema_version: "calibration.charuco_observations.v1" })).toBe("charucoObservations");
    expect(classifyArtifact({ schema_version: "calibration.mono.v1" })).toBe("monoPackage");
    expect(classifyArtifact({ package_type: "stereo_camera_calibration" })).toBe("stereoPackage");
    expect(classifyArtifact({ schema_version: "unknown" })).toBe("unknown");
  });

  test("summarizes workflow gates from imported artifacts", () => {
    const artifacts: ImportedArtifact[] = [
      artifact("manifest", "captureManifest", {
        schema_version: "calibration.capture_session.v1",
        topology: "stereo",
        session_id: "stereo_session",
        pair_count: 5,
      }),
      artifact("inspection", "captureInspection", {
        schema_version: "calibration.capture_inspection.v1",
        accepted: true,
        read_image_count: 10,
        image_count: 10,
      }),
      artifact("observations", "charucoObservations", {
        schema_version: "calibration.charuco_observations.v1",
        accepted: false,
        topology: "stereo",
        accepted_pair_count: 0,
        total_pair_count: 5,
      }),
    ];

    const stages = summarizeWorkflow(artifacts);

    expect(stages.map((stage) => stage.state)).toEqual(["ready", "ready", "blocked", "missing", "missing"]);
    expect(stages[0].detail).toContain("stereo_session");
    expect(stages[2].metric).toBe("0 / 5");
  });

  test("builds capture, review, detection, and solve commands", () => {
    expect(
      buildCaptureCommand({
        topology: "stereo",
        cameraId: "cam1",
        leftCameraId: "cam1",
        rightCameraId: "cam2",
        device: "/dev/video0",
        leftDevice: "/dev/video0",
        rightDevice: "/dev/video2",
        output: "../../artifacts/calibration_sessions/stereo",
        frameCount: 20,
        pairCount: 24,
        width: 1280,
        height: 720,
        intervalMs: 500,
        prepareUvcControls: true,
      }),
    ).toContain("--prepare-uvc-controls");
    expect(buildInspectCommand("session", "docs/report.md")).toContain("capture inspect");
    expect(buildDetectCommand("session", "session/observations.json", "docs/detect.md")).toContain("detect-charuco");
    expect(
      buildSolveCommand({
        topology: "stereo",
        observations: "session/observations.json",
        output: "artifacts/calibration/stereo_cam1_cam2",
        cameraId: "cam1",
        leftMono: "artifacts/calibration/cam1",
        rightMono: "artifacts/calibration/cam2",
        minViews: 8,
        minPairs: 12,
        maxRmsPx: 2,
      }),
    ).toContain("calibrate stereo");
  });

  test("extracts inspection and observation table rows", () => {
    expect(
      frameRows({
        frames: [{ path: "frames/cam1.png", side: "left", status: "read", mean_luma: 74, std_luma: 0.1, issues: ["blank"] }],
      }),
    ).toEqual([{ path: "frames/cam1.png", side: "left", status: "read", luma: "74", contrast: "0.1", issues: "blank" }]);

    expect(
      observationRows({
        views: [{ path: "frames/cam1.png", side: "left", accepted: true, corner_count: 104, marker_count: 63 }],
      }),
    ).toEqual([{ path: "frames/cam1.png", side: "left", accepted: "true", corners: "104", markers: "63", reason: "none" }]);
  });
});

function artifact(name: string, kind: ImportedArtifact["kind"], payload: Record<string, unknown>): ImportedArtifact {
  return { id: name, name, kind, payload };
}
