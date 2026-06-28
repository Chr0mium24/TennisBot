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

  const fixture = createFixture(defaultLive3dConfig);
  expect(fixture.status.some((item) => item.detail.includes("no real tracking validation"))).toBe(
    true,
  );
});
