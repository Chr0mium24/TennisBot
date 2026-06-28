import { expect, test } from "bun:test";
import { defaultLive3dConfig, describeFixtureMode } from "./config";
import { createFixture } from "./fixtures";

test("default config exposes runtime placeholders", () => {
  expect(defaultLive3dConfig.cameras.left.devicePath).toBe("/dev/video0");
  expect(defaultLive3dConfig.cameras.right.devicePath).toBe("/dev/video2");
  expect(defaultLive3dConfig.artifacts.yoloModelPackagePath).toContain(
    "artifacts/models",
  );
  expect(defaultLive3dConfig.artifacts.stereoCalibrationPackagePath).toContain(
    "artifacts/calibration",
  );
});

test("fixture mode is explicitly non-validating", () => {
  const description = describeFixtureMode(defaultLive3dConfig.mode);
  expect(description).toContain("Fixture mode");
  expect(description).toContain("does not validate");
  expect(description).toContain("USB cameras");
  expect(description).toContain("real YOLO inference");
  expect(description).toContain("real calibration");
  expect(description).toContain("real prediction");

  const fixture = createFixture(defaultLive3dConfig);
  expect(fixture.status.some((item) => item.detail.includes("USB cameras"))).toBe(true);
  expect(fixture.status.some((item) => item.detail.includes("real YOLO inference"))).toBe(
    true,
  );
  expect(fixture.status.some((item) => item.detail.includes("real calibration"))).toBe(
    true,
  );
  expect(fixture.status.some((item) => item.detail.includes("real prediction"))).toBe(
    true,
  );
});

test("fixture construction runs the core stereo and prediction flow", () => {
  const fixture = createFixture(defaultLive3dConfig);

  expect(fixture.calibration.rectifiedProjection).toBeDefined();
  expect(fixture.stereoPairing.match).toBe(fixture.selectedPair);
  expect(fixture.stereoPairing.diagnostics.evaluatedCandidateCount).toBe(2);
  expect(fixture.selectedPair.left.detectionId).toBe("fixture-left-2");
  expect(fixture.selectedPair.right.detectionId).toBe("fixture-right-2");
  expect(fixture.selectedPair.disparityPx).toBeGreaterThan(20);

  expect(fixture.scene.ball.sourcePairId).toBe(fixture.selectedPair.pairId);
  expect(fixture.scene.ball.positionMeters.x).toBeCloseTo(0.1, 8);
  expect(fixture.scene.ball.positionMeters.y).toBeCloseTo(0.04, 8);
  expect(fixture.scene.ball.positionMeters.z).toBeCloseTo(2.25, 8);
  expect(fixture.scene.ball.diagnostics?.averageReprojectionErrorPx).toBeCloseTo(0, 8);

  expect(fixture.scene.trail).toHaveLength(3);
  expect(fixture.scene.prediction.sourcePointIds).toEqual(
    fixture.scene.trail.map((point) => point.pointId),
  );
  expect(fixture.scene.prediction.samples).toHaveLength(9);
  expect(fixture.scene.prediction.samples[0]?.positionMeters).toEqual(
    fixture.scene.ball.positionMeters,
  );
  expect(fixture.scene.landing.sourcePredictionId).toBe(
    fixture.scene.prediction.predictionId,
  );
  expect(fixture.scene.landing.positionMeters.z).toBe(0);
});
