import { describe, expect, test } from "bun:test";
import {
  convertBackendYoloBoxesToDetections,
  createBlockedYoloInferenceBackend,
  detectionToOverlayBox,
  runYoloInferenceForFrame,
  type YoloInferenceBackend,
  type YoloInferenceFrame,
} from "./detections";

describe("Live3D YOLO detection adapter", () => {
  test("converts deterministic fake backend output for independent left and right frames", async () => {
    const backend: YoloInferenceBackend = {
      name: "fake-yolo",
      async infer(frame) {
        return {
          status: "ok",
          boxes: [
            frame.side === "left"
              ? {
                  detectionId: "left-ball",
                  confidence: 0.91,
                  xPx: 100,
                  yPx: 120,
                  widthPx: 28,
                  heightPx: 30,
                }
              : {
                  detectionId: "right-ball",
                  confidence: 0.87,
                  xPx: 74,
                  yPx: 121,
                  widthPx: 26,
                  heightPx: 29,
                },
          ],
        };
      },
    };

    const left = await runYoloInferenceForFrame(backend, frame("left", "cam-left", "frame-l"));
    const right = await runYoloInferenceForFrame(backend, frame("right", "cam-right", "frame-r"));

    expect(left.state).toBe("ready");
    expect(right.state).toBe("ready");
    expect(left.detections[0]).toMatchObject({
      detectionId: "left-ball",
      cameraId: "cam-left",
      frameId: "frame-l",
      label: "tennis_ball",
      confidence: 0.91,
      centerPx: { x: 114, y: 135 },
    });
    expect(right.detections[0]).toMatchObject({
      detectionId: "right-ball",
      cameraId: "cam-right",
      frameId: "frame-r",
      confidence: 0.87,
      centerPx: { x: 87, y: 135.5 },
    });
  });

  test("blocked backend returns blocked runtime status without throwing", async () => {
    const backend = createBlockedYoloInferenceBackend(
      "ONNX Runtime Web backend is not implemented in Wave 9.",
    );

    const status = await runYoloInferenceForFrame(backend, frame("left", "cam-left", "frame-l"));

    expect(status.state).toBe("blocked");
    expect(status.code).toBe("backend-blocked");
    expect(status.detail).toContain("ONNX Runtime Web backend is not implemented");
    expect(status.detections).toEqual([]);
  });

  test("clamps partially out-of-frame boxes and rejects malformed boxes", () => {
    const result = convertBackendYoloBoxesToDetections({
      cameraId: "cam-left",
      frameId: "frame-1",
      timestampUnixMs: 1_770_000_000_000,
      imageSize: { widthPx: 1280, heightPx: 720 },
      boxes: [
        {
          confidence: 0.8,
          xPx: -10,
          yPx: 700,
          widthPx: 30,
          heightPx: 50,
        },
        {
          confidence: 0.7,
          xPx: 10,
          yPx: 10,
          widthPx: -4,
          heightPx: 12,
        },
        {
          confidence: Number.NaN,
          xPx: 10,
          yPx: 10,
          widthPx: 12,
          heightPx: 12,
        },
      ],
    });

    expect(result.detections).toHaveLength(1);
    expect(result.detections[0].bboxPx).toEqual({
      xPx: 0,
      yPx: 700,
      widthPx: 20,
      heightPx: 20,
    });
    expect(result.detections[0].centerPx).toEqual({ x: 10, y: 710 });
    expect(result.warnings).toHaveLength(2);
  });

  test("converts runtime detections into percentage overlay boxes", () => {
    const [detection] = convertBackendYoloBoxesToDetections({
      cameraId: "cam-left",
      frameId: "frame-1",
      timestampUnixMs: 1_770_000_000_000,
      imageSize: { widthPx: 1280, heightPx: 720 },
      boxes: [{ confidence: 0.75, xPx: 320, yPx: 180, widthPx: 64, heightPx: 36 }],
    }).detections;

    expect(detectionToOverlayBox(detection, { widthPx: 1280, heightPx: 720 })).toEqual({
      label: "tennis_ball",
      confidence: 0.75,
      x: 25,
      y: 25,
      width: 5,
      height: 5,
    });
  });
});

function frame(
  side: YoloInferenceFrame["side"],
  cameraId: string,
  frameId: string,
): YoloInferenceFrame {
  return {
    side,
    cameraId,
    frameId,
    timestampUnixMs: 1_770_000_000_000,
    imageSize: { widthPx: 1280, heightPx: 720 },
  };
}
