# TennisBot Current Architecture

Date: 2026-06-29

## Current Shape

TennisBot is now a local-machine-first workspace. The active runtime code lives
in top-level `apps/`, `packages/`, and `tools/`. Local legacy lab code remains
under ignored `desperate/` when present. Calibration now uses the retained
original OpenCV `desperate/CameraCalibLab` workflow; the standalone
`tools/calibration` package has been deleted.

```text
TennisBot/
  apps/
    live3d/          browser USB stereo camera, YOLO inference, runtime 3D UI

  packages/
    contracts/       shared TypeScript data contracts
    core/            stereo pairing, triangulation, prediction, artifact loaders

  tools/
    yolo/            standalone YOLO model package tool

  artifacts/         ignored local runtime artifacts
    calibration/
    models/

  docs/              plans, results, reviews, runbooks
```

Ignored local legacy archive when present:

```text
desperate/CameraCalibLab/
desperate/TennisBallDetectorLab/
desperate/BallTrajectoryLab/
desperate/TennisWebSim/
```

They are not tracked by the parent repository and are not used as the main
runtime architecture. The old `TennisBotCV` integration/board-runtime shell was
retired from the main repository on 2026-06-29; see
`docs/legacy_board_retirement_20260629.md`.

## Boundaries

### `tools/yolo`

Owns YOLO package production and verification. It does not own Live3D runtime
state, stereo geometry, prediction, camera UI, or calibration.

Default runtime output:

```text
artifacts/models/tennis_ball_yolo/
```

### `desperate/CameraCalibLab`

Owns local OpenCV calibration capture and calibration artifact production when
the ignored local archive is present. Runtime code should still consume exported
calibration artifacts from `artifacts/calibration/...`; it should not import
CameraCalibLab source modules.

Default runtime output:

```text
artifacts/calibration/stereo_cam1_cam2/
```

### `packages/core`

Owns pure runtime algorithms and artifact metadata validation:

- YOLO and stereo calibration artifact metadata loaders;
- stereo detection pairing;
- rectified stereo triangulation;
- projectile trajectory prediction.

It has no YOLO training, calibration GUI, browser rendering, or device-specific
board code.

### `apps/live3d`

Owns the real-machine UI:

- opens two browser USB camera streams by explicit Start/Stop controls;
- loads YOLO and calibration artifact packages from `/artifacts/...`;
- uses `onnxruntime-web` for browser ONNX YOLO inference when a valid ONNX
  package is available;
- overlays runtime detections on both camera views;
- feeds left/right detections to `packages/core`;
- renders runtime 3D ball point, trail, prediction curve, and landing point;
- falls back to explicitly labelled fixture views when real runtime state is not
  available.

## Runtime Flow

```text
1. CameraCalibLab produces mono cam1 calibration artifacts
2. CameraCalibLab produces mono cam2 calibration artifacts
3. CameraCalibLab produces stereo calibration artifacts
4. tools/yolo package create/verify
5. apps/live3d loads /artifacts/models/tennis_ball_yolo
6. apps/live3d loads /artifacts/calibration/stereo_cam1_cam2
7. user starts two USB cameras in the browser
8. user starts YOLO backend
9. Live3D runs ONNX inference on left/right frames
10. Live3D selects stereo pair, triangulates 3D point, updates prediction
```

## Main Commands

Run Live3D:

```bash
cd apps/live3d
bun install
bun run dev
```

Verify Live3D:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/live3d_hardware_loop_YYYYMMDD.md
```

The hardware verifier writes a Markdown acceptance checklist for app server,
runtime snapshot, YOLO artifact, calibration artifact, stereo camera streams,
frame quality, left/right detections, stereo triangulation, and trajectory
prediction. The overall run only passes when Live3D reaches `prediction-ready`.
Readable scenes with no visible tennis ball are classified as blocked detection
gates in the report, not as completed validation.

Create dry-run YOLO artifacts:

```bash
cd tools/yolo
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Create runtime YOLO artifacts from existing local model files:

```bash
cd tools/yolo
uv run tennisbot-yolo package create \
  --output-dir ../../artifacts/models/tennis_ball_yolo \
  --model-pt ../../artifacts/model_candidates/finetune_indoor_cam1/best.pt \
  --model-onnx ../../artifacts/model_candidates/finetune_indoor_cam1/best.onnx \
  --default-model onnx \
  --eval-report ../../artifacts/model_candidates/finetune_indoor_cam1/eval_report.md \
  --eval-metrics ../../artifacts/model_candidates/finetune_indoor_cam1/eval_metrics.json
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Verify packages:

```bash
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
```

Run the original OpenCV stereo calibration GUI:

```bash
cd desperate/CameraCalibLab
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --config configs/dfoptix_charuco_15mm_capture.yaml \
  --output captures/local/dfoptix_stereo_charuco_auto_session \
  --calibration-output runs/calibrations/dfoptix_stereo_charuco_auto \
  --views 30 \
  --left-device /dev/video0 \
  --right-device /dev/video2
```

## Current Verification Evidence

Most recent software verification:

```text
cd apps/live3d && bun test
Result: 44 passing tests, 0 failures.

cd apps/live3d && bun run typecheck
Result: passed.

cd apps/live3d && bun run build
Result: passed.
```

The software path is connected through Live3D, ONNX backend boundary, core
stereo triangulation, and prediction using synthetic tests.

Live3D also exposes `window.__tennisbotLive3dSnapshot` for repeatable hardware
checks. The verifier command can launch Chrome, start both USB cameras, start
YOLO, capture left/right frame PNGs with brightness statistics, and poll the
snapshot until runtime 3D reaches `prediction-ready` or a Markdown report
records the failed gate. For the current local USU Camera 4K devices, the
browser request is `1280x720@30`; direct V4L2 tests showed `1280x720` MJPG
works while high-resolution YUYV times out. `--prepare-uvc-controls` can apply
the high-brightness UVC controls that recovered non-black browser frames.

Runtime artifacts have also been imported locally:

```text
YOLO: dry_run=false, inference_ready=true, default_model=onnx.
YOLO static smoke: 109/109 matched labeled samples detected at threshold 0.05.
Calibration: dry_run=false, hardware_validated=true, package verify accepted.
Calibration scanned import: 17 CameraCalibLab calibration files scanned,
selected cam1/cam2 by path pattern, ranked 3 stereo candidates, and imported
best stereo candidate dfoptix_charuco_stereo_auto_fixed_intrinsics_rational_20260622.
Calibration target sheet: docs/calibration_charuco_target_sheet_20260629.md
records the generated DFOptix ChArUco 14x9 `DICT_5X5_100` sheet. The printable
artifacts live under artifacts/calibration_targets/ and use 15 mm squares,
11 mm markers, and a 210 mm x 135 mm board.
Calibration quality warning: epipolar_rms=4.330 px exceeds the 2.000 px
runtime-quality review threshold. stereo_rms=0.424 px,
rectification_y_p95=0.830 px, baseline=0.052486 m.
Calibration capture sessions: historical dry-run mono/stereo sessions wrote
manifests, frames, summary, and review files; a real 1-pair stereo hardware
probe opened /dev/video0 and /dev/video2 at 1280x720 MJPG. The retained
calibration path is now the original CameraCalibLab OpenCV workflow.
```

Latest recalibrated hardware smoke:

```text
Report: docs/live3d_hardware_loop_recalibrated_20260629.md
Loaded calibration baselineMeters: 0.05248616443700974
Camera path: two USU Camera 4K browser captures at 1280x720@30.
Frame quality: left/right captures are non-black after UVC preparation.
Remaining gate: no visible tennis ball was detected, so runtime 3D stayed at
left-detections-missing instead of prediction-ready.
```

Latest hardware acceptance probe:

```text
Report: docs/live3d_hardware_acceptance_probe_20260629.md
Checklist passed: app server, runtime snapshot, YOLO artifact, calibration
artifact, stereo USB camera streams, and readable left/right camera frames.
Checklist blocked: left/right YOLO detection because no visible tennis ball was
present in the current scene.
Remaining gate: stereo triangulation and prediction are waiting on live
left/right ball detections.
```

## Remaining Physical Validation

The architecture is implemented in software. These items still require real
hardware validation:

- keep the UVC brightness/exposure preparation or equivalent physical lighting
  so both USB camera frames are non-black;
- capture real mono/stereo calibration sessions with visible ChArUco targets and
  `capture inspect` plus `capture detect-charuco` accepted before solving;
- run `calibrate mono` on real `cam1` and `cam2` sessions and review RMS before
  replacing imported historical calibration;
- run `calibrate stereo` on real stereo observations and review stereo RMS,
  baseline, and rectification before replacing imported historical calibration;
- rerun the Live3D hardware verifier with a tennis ball visible in both USB
  camera views;
- verify nonzero ONNX detections on both live frames;
- verify runtime 3D reaches `prediction-ready` with stable point and prediction
  updates;
- re-run stereo calibration if the remaining epipolar RMS warning must be
  reduced below the runtime-quality review threshold;
- validate ROS/Gazebo closed-loop catch behavior only after the real visual
  tracking path is stable.
