# TennisBot Final Runtime Validation

Date: 2026-06-29

## Scope

This validation covers the current local-machine software architecture:

- `packages/contracts`
- `packages/core`
- `tools/calibration`
- `tools/yolo`
- `apps/live3d`

It does not claim ROS/Gazebo catch control or final physical 3D accuracy. A
real local YOLO package and an imported real calibration package are available
for runtime smoke testing. Live3D has also opened two real USB cameras in
Chrome and run the ONNX backend loop. The camera path now requests
`1280x720@30`, matching the local UVC modes. Direct V4L2 diagnostics showed
MJPG streams work at `1280x720`; high-resolution YUYV streams time out. Applying
high-brightness UVC controls recovered non-black browser frames, but the current
scene still contains no visible tennis ball. The imported stereo calibration
now uses the selected rational fixed-intrinsics CameraCalibLab result; it has a
remaining epipolar RMS quality warning.

Follow-up YOLO static validation found that Live3D was decoding the exported
ONNX `xyxy_pixels` output as `xywh`. That postprocessing bug is fixed. The
initial `detector_package` model failed the static quality check, so the local
runtime package was rebuilt from
`TennisBallDetectorLab/yolo/runs/training/finetune_indoor_cam1/weights/best.pt`
and an exported ONNX model. The rebuilt package detects 109/109 matched labeled
samples at `confidence_threshold: 0.05`.

## Verified Commands

### Contracts

```bash
cd packages/contracts
bun test
bun run typecheck
```

Result: 4 tests passed, typecheck passed.

### Core

```bash
cd packages/core
bun test
bun run typecheck
```

Result: 21 tests passed, typecheck passed.

### Live3D

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 20000 --output ../../docs/live3d_hardware_loop_recalibrated_20260629.md
```

Result: 42 tests passed, typecheck passed, browser bundle built. The hardware
verification command wrote
`docs/live3d_hardware_loop_recalibrated_20260629.md`; it loaded the refreshed
calibration baseline `0.05248616443700974`, captured non-black left/right
frames, and failed only because the live scene had no detectable tennis ball.

Dev server smoke:

```bash
PORT=5178 bun ./scripts/serve.js
curl -I http://localhost:5178/
curl -I http://localhost:5178/assets/main.js
curl -I http://localhost:5178/artifacts/models/tennis_ball_yolo/package.json
curl -I http://localhost:5178/artifacts/calibration/stereo_cam1_cam2/package.json
```

Result: all HTTP checks returned `200 OK`.

Hardware smoke:

```bash
v4l2-ctl --list-devices
ffmpeg ... -i /dev/video0 ... -i /dev/video2 ...
google-chrome --headless=new --use-fake-ui-for-media-stream ...
```

Result: two `USU Camera 4K` devices were enumerated, `/dev/video0` and
`/dev/video2` were opened simultaneously, Chrome opened distinct left/right
`MediaStream` tracks at 1280x720, and the ONNX backend ran continuously against
browser camera sources without ONNX session errors. With default UVC controls,
the verifier saved near-black left/right browser frame captures. After applying
high-brightness UVC controls, the verifier saved non-black captures but still
produced zero YOLO detections because the scene is uniform gray and contains no
visible tennis ball.

Automated hardware loop:

```bash
bun apps/live3d/scripts/verify-hardware.ts \
  --prepare-uvc-controls \
  --timeout-ms 20000 \
  --output docs/live3d_hardware_loop_recalibrated_20260629.md
```

Result: the script applied brightness `64`, gain `255`, manual exposure `2047`
to `/dev/video0` and `/dev/video2`, reused `http://localhost:5178`, launched
`/usr/bin/google-chrome` on CDP port `9233`, found
`window.__tennisbotLive3dSnapshot`, opened two real `USU Camera 4K` browser
streams, loaded the ONNX YOLO artifact, and loaded the stereo calibration
artifact with baseline `0.05248616443700974`. Captured browser frames were
non-black (`mean_luma` about `68`, `non_black_pixel_percent: 100%`) but still
had zero YOLO tennis-ball detections.
Last runtime code: `left-detections-missing`.

Direct V4L2 cross-check:

```bash
v4l2-ctl -d /dev/video0 --list-formats-ext
v4l2-ctl -d /dev/video2 --list-formats-ext
timeout 5s v4l2-ctl -d /dev/video0 --set-fmt-video=width=1280,height=720,pixelformat=MJPG --stream-mmap --stream-count=1 --stream-to=artifacts/hardware_smoke/20260629/direct_v4l2_frames/video0_MJPG_1280x720.raw
timeout 5s v4l2-ctl -d /dev/video2 --set-fmt-video=width=1280,height=720,pixelformat=MJPG --stream-mmap --stream-count=1 --stream-to=artifacts/hardware_smoke/20260629/direct_v4l2_frames/video2_MJPG_1280x720.raw
timeout 5s v4l2-ctl -d /dev/video0 --set-fmt-video=width=1280,height=720,pixelformat=YUYV --stream-mmap --stream-count=1 --stream-to=artifacts/hardware_smoke/20260629/direct_v4l2_frames/video0_YUYV_1280x720.raw
timeout 5s v4l2-ctl -d /dev/video2 --set-fmt-video=width=1280,height=720,pixelformat=YUYV --stream-mmap --stream-count=1 --stream-to=artifacts/hardware_smoke/20260629/direct_v4l2_frames/video2_YUYV_1280x720.raw
```

Result: both devices advertise `1280x720` MJPG and YUYV at 30 fps. Explicit
MJPG streaming succeeds immediately on both devices and writes JPEG frames.
Explicit YUYV streaming at `1280x720` times out with exit code `124` and writes
0-byte raw files. With default exposure, MJPG frames were very dark
(`mean_luma` about `4`, `max_luma` about `12`). After setting brightness `64`,
gain `255`, manual exposure `2047`, MJPG frames rose to `mean_luma` about `74`.

### Calibration Tool

```bash
cd tools/calibration
uv run pytest -q
uv run tennisbot-calibration capture mono --camera-id cam1 --device /dev/video0 --output ../../artifacts/calibration_sessions/20260629_cam1_dry_run --frame-count 3 --interval-ms 0 --width 320 --height 180 --dry-run
uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_dry_run --pair-count 3 --interval-ms 0 --width 320 --height 180 --dry-run
timeout 12s uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_hardware_probe --pair-count 1 --interval-ms 0 --width 1280 --height 720 --fourcc MJPG --fps 30
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package import-scanned-camera-calib-lab \
  --root ../../CameraCalibLab/runs/calibrations \
  --cam1-pattern dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7 \
  --cam2-pattern dfoptix_charuco_auto_cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --limit 12 \
  --output-report ../../docs/calibration_candidate_scan_20260629.md
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Result: 13 tests passed. Dry-run mono and stereo package generation still works.
Standalone capture sessions now write manifests, PNG frames, summary files, and
review HTML. The real stereo capture probe opened `/dev/video0` and
`/dev/video2` at 1280x720 MJPG and wrote one pair, but the scene was uniform gray
with no visible calibration target, so it is not sufficient for a solve.
The scanned import command selected cam1/cam2 mono candidates by path pattern,
ranked 3 stereo candidates, imported the best ranked CameraCalibLab rational
fixed-intrinsics stereo output into `artifacts/calibration/stereo_cam1_cam2`, and
verified it with `accepted: true`, `dry_run: false`, and `hardware_validated:
true`.

Imported calibration quality warning:

```text
baseline_m: 0.05248616443700974
stereo_rms_reprojection_px: 0.42365210023675176
epipolar_rms_px: 4.3304497343502
rectification_y_p95_px: 0.8301635742187499
```

### YOLO Tool

```bash
cd tools/yolo
uv run pytest -q
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package create \
  --output-dir ../../artifacts/models/tennis_ball_yolo \
  --model-pt ../../artifacts/model_candidates/finetune_indoor_cam1/best.pt \
  --model-onnx ../../artifacts/model_candidates/finetune_indoor_cam1/best.onnx \
  --default-model onnx \
  --eval-report ../../artifacts/model_candidates/finetune_indoor_cam1/eval_report.md \
  --eval-metrics ../../artifacts/model_candidates/finetune_indoor_cam1/eval_metrics.json
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Result: 13 tests passed. A real runtime YOLO package was written from the
`finetune_indoor_cam1` best model and verified with `dry_run: false`,
`inference_ready: true`, `default_model: onnx`, and static smoke
`detected_at_threshold: 109 / 109`.

## Current Evidence

- YOLO and calibration are separate standalone tool packages under `tools/`.
- Live3D consumes only model/calibration artifacts under `artifacts/`.
- Runtime core algorithms live under `packages/core`.
- Shared data contracts live under `packages/contracts`.
- `artifacts/models/tennis_ball_yolo` now contains a real ONNX-default package
  rebuilt from `finetune_indoor_cam1/weights/best.pt`.
- `artifacts/calibration/stereo_cam1_cam2` now contains a real imported stereo
  package from the selected rational fixed-intrinsics CameraCalibLab result.
- `tools/calibration` now has standalone mono and stereo capture session
  commands. Dry-run sessions are deterministic, and a real stereo hardware probe
  opened `/dev/video0` plus `/dev/video2` and wrote one 1280x720 MJPG pair.
- The current calibration package verifies with baseline
  `0.05248616443700974`, stereo RMS `0.42365210023675176`, rectification y p95
  `0.8301635742187499`, and a remaining epipolar RMS `4.3304497343502`
  warning.
- Live3D opened two real USB cameras in Chrome at `1280x720@30` and ran the
  ONNX backend loop without session concurrency errors.
- The recalibrated Live3D hardware report loaded baselineMeters
  `0.05248616443700974` and captured non-black frames after UVC preparation.
- Live3D now has a repeatable headless hardware verifier that reads
  `window.__tennisbotLive3dSnapshot` and records camera, YOLO, calibration,
  detection, runtime 3D state, frame captures, and frame brightness statistics
  to Markdown.
- Live3D now decodes the current ONNX package's `xyxy_pixels` output correctly.
- The current YOLO model package passed the static detection-quality smoke at
  `confidence_threshold: 0.05` on 109 matched labeled images.
- Board-side runtime code is not part of the current active architecture.
- The only dirty worktree entry after validation is the pre-existing
  `TennisBallDetectorLab` submodule state, which remains untouched.

## Remaining Physical Validation

Before claiming full real-world operation:

1. Keep `--prepare-uvc-controls` or equivalent lighting/exposure adjustment so
   both browser captures are non-black.
2. Put a tennis ball in both USB camera views and rerun
   `bun apps/live3d/scripts/verify-hardware.ts --prepare-uvc-controls --timeout-ms 30000 --output docs/live3d_hardware_loop_ball_YYYYMMDD.md`
   until the report reaches `prediction-ready`.
3. Confirm runtime 3D scene, prediction curve, and landing marker update from
   those detections.
4. Re-run or refine stereo calibration if the remaining epipolar RMS warning
   must be reduced below the runtime-quality review threshold.
5. Validate ROS/Gazebo closed-loop catch behavior only after real visual
   tracking is stable.
