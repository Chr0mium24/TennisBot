import { describe, expect, test } from "bun:test";

import {
  buildCaptureCommand,
  buildDetectCommand,
  buildInspectCommand,
  buildSolveCommand,
  buildTargetCommand,
  buildTargetPrintCheckCommand,
  buildVerifyCommand,
  captureFramePreviews,
  classifyArtifact,
  frameRows,
  observationRows,
  summarizeWorkflow,
  targetSheetFileLinks,
  targetPrintCheckReadiness,
  type ImportedArtifact,
} from "./calibration-workspace";

describe("calibration review workspace", () => {
  test("classifies calibration JSON artifacts", () => {
    expect(classifyArtifact({ schema_version: "calibration.target_sheet.v1" })).toBe("targetSheet");
    expect(classifyArtifact({ schema_version: "calibration.target_print_check.v1" })).toBe("targetPrintCheck");
    expect(classifyArtifact({ schema_version: "calibration.capture_session.v1" })).toBe("captureManifest");
    expect(classifyArtifact({ schema_version: "calibration.capture_inspection.v1" })).toBe("captureInspection");
    expect(classifyArtifact({ schema_version: "calibration.charuco_observations.v1" })).toBe("charucoObservations");
    expect(classifyArtifact({ schema_version: "calibration.package_verification.v1" })).toBe("packageVerification");
    expect(classifyArtifact({ schema_version: "calibration.mono.v1" })).toBe("monoPackage");
    expect(classifyArtifact({ package_type: "stereo_camera_calibration" })).toBe("stereoPackage");
    expect(classifyArtifact({ schema_version: "unknown" })).toBe("unknown");
  });

  test("summarizes workflow gates from imported artifacts", () => {
    const artifacts: ImportedArtifact[] = [
      artifact("target", "targetSheet", {
        schema_version: "calibration.target_sheet.v1",
        accepted: true,
        target: { profile: "dfoptix_charuco_15mm", squares_x: 14, squares_y: 9, square_size_m: 0.015 },
      }),
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

    expect(stages.map((stage) => stage.state)).toEqual(["ready", "missing", "ready", "ready", "blocked", "missing", "missing"]);
    expect(stages[0].detail).toContain("dfoptix_charuco_15mm");
    expect(stages[2].detail).toContain("stereo_session");
    expect(stages[4].metric).toBe("0 / 5");
  });

  test("builds capture, review, detection, and solve commands", () => {
    expect(
      buildTargetCommand({
        output: "../../artifacts/calibration_targets/target.png",
        outputReport: "../../docs/calibration_target.md",
        dpi: 300,
        marginMm: 10,
      }),
    ).toContain("target charuco");
    expect(
      buildTargetPrintCheckCommand({
        measuredSquareMm: 15.05,
        toleranceMm: 0.2,
        targetMetadata: "../../artifacts/calibration_targets/target.json",
        output: "../../artifacts/calibration_targets/print_check.json",
        outputReport: "../../docs/calibration_target_print_check.md",
      }),
    ).toContain("--target-metadata ../../artifacts/calibration_targets/target.json");
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
    expect(buildVerifyCommand("../../artifacts/calibration/stereo_cam1_cam2")).toContain("package verify");
  });

  test("requires an explicit measured print-check square size", () => {
    const base = {
      toleranceMm: 0.2,
      targetMetadata: "../../artifacts/calibration_targets/target.json",
      output: "../../artifacts/calibration_targets/print_check.json",
      outputReport: "../../docs/calibration_target_print_check.md",
    };

    expect(targetPrintCheckReadiness({ ...base, measuredSquareMm: 0 })).toMatchObject({ ready: false });
    expect(targetPrintCheckReadiness({ ...base, measuredSquareMm: Number.NaN })).toMatchObject({ ready: false });
    expect(targetPrintCheckReadiness({ ...base, measuredSquareMm: 15.02 })).toMatchObject({ ready: true });
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

  test("builds local capture frame previews from manifest and inspection artifacts", () => {
    const previews = captureFramePreviews(
      {
        schema_version: "calibration.capture_session.v1",
        topology: "stereo",
        session_id: "stereo_session",
        camera_ids: ["cam1", "cam2"],
        pairs: [{ index: 1, left: "frames/cam1_0001.png", right: "frames/cam2_0001.png" }],
      },
      {
        schema_version: "calibration.capture_inspection.v1",
        session_path: "../../artifacts/calibration_sessions/stereo_session",
        frames: [
          {
            path: "frames/cam1_0001.png",
            side: "left",
            camera_id: "cam1",
            index: 1,
            status: "read",
            width: 1280,
            height: 720,
            mean_luma: 74.002,
            std_luma: 0.048,
            issues: ["low contrast / likely blank frame"],
          },
        ],
      },
    );

    expect(previews).toHaveLength(2);
    expect(previews[0]).toMatchObject({
      path: "frames/cam1_0001.png",
      side: "left",
      cameraId: "cam1",
      status: "read",
      luma: "74.002",
      contrast: "0.048",
      size: "1280x720",
      issues: "low contrast / likely blank frame",
      imageUrl: "/artifacts/calibration_sessions/stereo_session/frames/cam1_0001.png",
    });
    expect(previews[1]).toMatchObject({
      path: "frames/cam2_0001.png",
      side: "right",
      cameraId: "cam2",
      status: "captured",
      imageUrl: "/artifacts/calibration_sessions/stereo_session/frames/cam2_0001.png",
    });
  });

  test("does not build preview URLs outside the artifacts directory", () => {
    const previews = captureFramePreviews(
      {
        schema_version: "calibration.capture_session.v1",
        topology: "mono",
        session_path: "../../artifacts/calibration_sessions/session",
        camera_id: "cam1",
        files: ["../secret.png", "frames/cam1_0001.png"],
      },
      undefined,
    );

    expect(previews[0].imageUrl).toBeUndefined();
    expect(previews[1].imageUrl).toBe("/artifacts/calibration_sessions/session/frames/cam1_0001.png");
  });

  test("builds printable target sheet file links from artifact metadata", () => {
    expect(
      targetSheetFileLinks({
        schema_version: "calibration.target_sheet.v1",
        files: {
          svg: "../../artifacts/calibration_targets/target.svg",
          png: "../../artifacts/calibration_targets/target.png",
          metadata: "../../artifacts/calibration_targets/target.json",
        },
      }),
    ).toEqual([
      {
        label: "svg",
        path: "../../artifacts/calibration_targets/target.svg",
        url: "/artifacts/calibration_targets/target.svg",
      },
      {
        label: "png",
        path: "../../artifacts/calibration_targets/target.png",
        url: "/artifacts/calibration_targets/target.png",
      },
      {
        label: "metadata",
        path: "../../artifacts/calibration_targets/target.json",
        url: "/artifacts/calibration_targets/target.json",
      },
    ]);
  });

  test("does not link target files outside served artifact paths", () => {
    expect(
      targetSheetFileLinks({
        schema_version: "calibration.target_sheet.v1",
        files: {
          svg: "../../docs/target.svg",
          png: "../../artifacts/../secret.png",
        },
      }),
    ).toEqual([
      { label: "svg", path: "../../docs/target.svg", url: undefined },
      { label: "png", path: "../../artifacts/../secret.png", url: undefined },
    ]);
  });
});

function artifact(name: string, kind: ImportedArtifact["kind"], payload: Record<string, unknown>): ImportedArtifact {
  return { id: name, name, kind, payload };
}
