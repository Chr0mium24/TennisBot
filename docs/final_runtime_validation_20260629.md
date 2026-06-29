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

Result: 45 tests passed, typecheck passed, browser bundle built. The hardware
verification command wrote
`docs/live3d_hardware_loop_recalibrated_20260629.md`; it loaded the refreshed
calibration baseline `0.05248616443700974`, captured non-black left/right
frames, and failed only because the live scene had no detectable tennis ball.
The verifier report renderer now also includes a fixed acceptance checklist for
server, snapshot, artifacts, stereo cameras, frame quality, left/right
detections, triangulation, and prediction. Unit tests cover the no-ball
classification as blocked detection gates and the `prediction-ready` success
case. Shared runtime readiness gates now cover the browser UI and snapshot.
The hardware verifier report also renders those snapshot gates as a dedicated
Runtime Readiness Gates section, so a saved Markdown report shows the same
ready/pending/blocked sequence as the browser status panel.

Dev server smoke:

```bash
cd ../../
bun scripts/start-local-runtime.ts --status
cd apps/live3d
PORT=5178 bun ./scripts/serve.js
curl -I http://localhost:5178/
curl -I http://localhost:5178/assets/main.js
curl -I http://localhost:5178/artifacts/models/tennis_ball_yolo/package.json
curl -I http://localhost:5178/artifacts/calibration/stereo_cam1_cam2/package.json
```

Result: the local runtime launcher status check reported Live3D and Calibration
GUI ready at `http://127.0.0.1:5178/` and `http://127.0.0.1:5188/`; all HTTP
checks returned `200 OK`.

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
uv run tennisbot-calibration target charuco --output ../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png --output-report ../../docs/calibration_charuco_target_sheet_20260629.md
uv run tennisbot-calibration capture mono --camera-id cam1 --device /dev/video0 --output ../../artifacts/calibration_sessions/20260629_cam1_dry_run --frame-count 3 --interval-ms 0 --width 320 --height 180 --dry-run
uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_dry_run --pair-count 3 --interval-ms 0 --width 320 --height 180 --dry-run
timeout 12s uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_hardware_probe --pair-count 1 --interval-ms 0 --width 1280 --height 720 --fourcc MJPG --fps 30
uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_quality_dry_run --pair-count 2 --interval-ms 0 --width 320 --height 180 --prepare-uvc-controls --dry-run
uv run tennisbot-calibration capture inspect --session ../../artifacts/calibration_sessions/20260629_stereo_quality_dry_run --output-report ../../docs/calibration_capture_quality_20260629.md
timeout 20s uv run tennisbot-calibration capture stereo --left-camera-id cam1 --right-camera-id cam2 --left-device /dev/video0 --right-device /dev/video2 --output ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe --pair-count 1 --interval-ms 0 --width 1280 --height 720 --fourcc MJPG --fps 30 --prepare-uvc-controls
uv run tennisbot-calibration capture inspect --session ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe --output-report ../../docs/calibration_capture_quality_hardware_probe_20260629.md || true
# Before this dry-run detection, frames/cam1_0001.png was replaced with a rendered DFOptix ChArUco target.
uv run tennisbot-calibration capture detect-charuco --session ../../artifacts/calibration_sessions/20260629_charuco_detection_dry_run --output ../../artifacts/calibration_sessions/20260629_charuco_detection_dry_run/observations.json --output-report ../../docs/calibration_charuco_detection_20260629.md
uv run tennisbot-calibration capture detect-charuco --session ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe --output ../../artifacts/calibration_sessions/20260629_stereo_quality_hardware_probe/observations.json --output-report ../../docs/calibration_charuco_detection_hardware_probe_20260629.md || true
# Before this mono solve dry-run, the five session frames were replaced with rendered/perspective-warped DFOptix ChArUco targets.
uv run tennisbot-calibration capture inspect --session ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run --output-report ../../docs/calibration_mono_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco --session ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run --output ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run/observations.json --output-report ../../docs/calibration_charuco_detection_mono_solve_20260629.md
uv run tennisbot-calibration calibrate mono --observations ../../artifacts/calibration_sessions/20260629_cam1_mono_solve_dry_run/observations.json --output ../../artifacts/calibration/cam1_mono_solve_dry_run --min-views 3 --max-rms-px 5
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/cam1_mono_solve_dry_run
# Before the stereo solve dry-run, cam2 mono and stereo frames were replaced with rendered/perspective-warped DFOptix ChArUco targets.
uv run tennisbot-calibration capture inspect --session ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run --output-report ../../docs/calibration_cam2_mono_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco --session ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run --output ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run/observations.json --output-report ../../docs/calibration_charuco_detection_cam2_mono_solve_20260629.md
uv run tennisbot-calibration calibrate mono --observations ../../artifacts/calibration_sessions/20260629_cam2_mono_solve_dry_run/observations.json --output ../../artifacts/calibration/cam2_mono_solve_dry_run --min-views 3 --max-rms-px 5
uv run tennisbot-calibration capture inspect --session ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run --output-report ../../docs/calibration_stereo_solve_capture_quality_20260629.md
uv run tennisbot-calibration capture detect-charuco --session ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run --output ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run/observations.json --output-report ../../docs/calibration_charuco_detection_stereo_solve_20260629.md
uv run tennisbot-calibration calibrate stereo --observations ../../artifacts/calibration_sessions/20260629_stereo_solve_dry_run/observations.json --left-mono ../../artifacts/calibration/cam1_mono_solve_dry_run --right-mono ../../artifacts/calibration/cam2_mono_solve_dry_run --output ../../artifacts/calibration/stereo_solve_dry_run --min-pairs 3 --max-rms-px 50
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_solve_dry_run
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

Result: 20 tests passed. Dry-run mono and stereo package generation still works.
The target generator writes a printable PNG/SVG/metadata bundle plus the
Markdown report `docs/calibration_charuco_target_sheet_20260629.md` for the
DFOptix 14x9 `DICT_5X5_100` sheet. Standalone capture sessions now write
manifests, PNG frames, summary files, and review HTML. `capture inspect` writes
`inspection.json` and optional Markdown reports before target detection or
solve. The quality-gated dry-run stereo session accepted 4/4 images. The real
stereo capture probe applied UVC controls, opened `/dev/video0` and
`/dev/video2` at 1280x720 MJPG, wrote one pair, then rejected both images as low
contrast / likely blank, so the current scene is not sufficient for a solve.
`capture detect-charuco` now writes observation JSON and Markdown reports for
the DFOptix 14x9 `DICT_5X5_100` ChArUco profile. A rendered target dry-run
detected 104 corners and 63 markers; the current real hardware probe detected 0
ChArUco corners in both views. `calibrate mono` now consumes accepted ChArUco
observations and writes a mono runtime package. The rendered mono solve dry-run
accepted 5/5 views, produced
`rms_reprojection_px=3.551100557082021` with the intentionally relaxed 5 px
dry-run threshold, and `package verify` accepted the mono package.
`calibrate stereo` now consumes accepted stereo ChArUco observations plus two
mono packages and writes a runtime stereo package. The rendered stereo solve
dry-run accepted 5/5 pairs, produced
`stereo_rms_reprojection_px=3.5982434312593963`, baseline
`0.03480523495236254`, and `package verify` accepted the stereo package.
The scanned import command selected cam1/cam2 mono candidates by path pattern,
ranked 3 stereo candidates, imported the best ranked CameraCalibLab rational
fixed-intrinsics stereo output into `artifacts/calibration/stereo_cam1_cam2`, and
verified it with `accepted: true`, `dry_run: false`, and `hardware_validated:
true`.

### Calibration Review GUI

```bash
cd tools/calibration/frontend/review
bun test
bun run build
```

Result: 12 tests passed and the browser bundle built. The review GUI imports
artifact-shaped JSON, summarizes target/capture/inspect/detect/mono/stereo
gates, renders local capture PNG frame previews, inspection and ChArUco tables,
displays package metrics, generates the next CLI commands, and can execute
whitelisted calibration CLI commands through its local Bun server. The GUI
starts the visible workflow with `target charuco`, then capture, inspect,
detect, solve, and package verify. The `Cam1 Mono`, `Cam2 Mono`, and `Stereo`
presets keep capture, observations, solve, report, and verify paths aligned.
Command results return generated JSON artifacts for automatic workspace import.
It does not import Python calibration internals or legacy lab source modules.

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
- `bun scripts/start-local-runtime.ts` is the root local operator launcher for
  Live3D plus the Calibration GUI; `--status` verifies both URLs without
  starting new services.
- Runtime core algorithms live under `packages/core`.
- Shared data contracts live under `packages/contracts`.
- `artifacts/models/tennis_ball_yolo` now contains a real ONNX-default package
  rebuilt from `finetune_indoor_cam1/weights/best.pt`.
- `artifacts/calibration/stereo_cam1_cam2` now contains a real imported stereo
  package from the selected rational fixed-intrinsics CameraCalibLab result.
- `tools/calibration` now has standalone mono and stereo capture session
  commands. Dry-run sessions are deterministic, and a real stereo hardware probe
  opened `/dev/video0` plus `/dev/video2` and wrote one 1280x720 MJPG pair.
  The tool also generates the printable ChArUco target sheet used for physical
  mono/stereo capture. Capture sessions can apply the local UVC exposure preset
  and run `capture inspect` plus `capture detect-charuco` as pre-solve gates.
  `calibrate mono` can solve and package accepted mono observations.
  `calibrate stereo` can solve and package accepted stereo observations with two
  mono packages.
- The current calibration package verifies with baseline
  `0.05248616443700974`, stereo RMS `0.42365210023675176`, rectification y p95
  `0.8301635742187499`, and a remaining epipolar RMS `4.3304497343502`
  warning.
- Live3D opened two real USB cameras in Chrome at `1280x720@30` and ran the
  ONNX backend loop without session concurrency errors.
- The recalibrated Live3D hardware report loaded baselineMeters
  `0.05248616443700974` and captured non-black frames after UVC preparation.
- `docs/live3d_hardware_acceptance_probe_20260629.md` reran the current
  hardware verifier after checklist reporting was added. It passed server,
  snapshot, artifact, stereo camera, and frame-quality gates, then marked
  left/right YOLO detection as blocked because no visible tennis ball was
  present.
- `docs/live3d_hardware_readiness_gates_20260629.md` reran the hardware
  verifier after Runtime Readiness Gates were added. It passed app server,
  snapshot, YOLO artifact, calibration artifact, stereo cameras, and readable
  non-black frames, then showed left/right detection, stereo 3D point, and
  prediction as pending because no tennis ball was visible to YOLO.
- Live3D now has a repeatable headless hardware verifier that reads
  `window.__tennisbotLive3dSnapshot` and records camera, YOLO, calibration,
  detection, runtime 3D state, frame captures, and frame brightness statistics
  to Markdown.
- Live3D now publishes and renders runtime readiness gates for YOLO artifact,
  calibration artifact, stereo cameras, left/right detections, stereo 3D point,
  and prediction so the browser UI shows the same blocked/pending/ready sequence
  as the hardware verifier report.
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
