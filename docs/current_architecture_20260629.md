# TennisBot Current Architecture

Date: 2026-06-29

## Current Shape

TennisBot is now a local-machine-first workspace. The active runtime code lives
in top-level `apps/`, `packages/`, and `tools/`; older lab directories remain
as legacy/reference submodules and are not the runtime boundary.

```text
TennisBot/
  apps/
    live3d/          browser USB stereo camera, YOLO inference, runtime 3D UI

  packages/
    contracts/       shared TypeScript data contracts
    core/            stereo pairing, triangulation, prediction, artifact loaders

  tools/
    calibration/     standalone calibration package tool
      frontend/review calibration artifact review GUI
    yolo/            standalone YOLO model package tool

  artifacts/         ignored local runtime artifacts
    calibration/
    models/

  docs/              plans, results, reviews, runbooks
```

Legacy/reference submodules still present:

```text
CameraCalibLab/
TennisBallDetectorLab/
BallTrajectoryLab/
TennisWebSim/
```

They are not used as the main runtime architecture. `TennisBallDetectorLab`
currently has user-owned dirty state and remains untouched. The old
`TennisBotCV` integration/board-runtime shell was retired from the main
repository on 2026-06-29; see `docs/legacy_board_retirement_20260629.md`.

## Boundaries

### `tools/yolo`

Owns YOLO package production and verification. It does not own Live3D runtime
state, stereo geometry, prediction, camera UI, or calibration.

Default runtime output:

```text
artifacts/models/tennis_ball_yolo/
```

### `tools/calibration`

Owns mono/stereo calibration package production and verification. It does not
own YOLO inference, trajectory prediction, or Live3D rendering. It can import
existing CameraCalibLab calibration JSON into the runtime artifact contract
without making the main runtime depend on CameraCalibLab source code.
It also owns an isolated TypeScript/Bun review GUI under
`tools/calibration/frontend/review` for artifact-shaped JSON review and command
handoff. The GUI server includes a local-only whitelist command bridge for
running reviewed calibration CLI commands and returning generated JSON artifacts
to the browser workspace.

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
1. tools/calibration mono cam1
2. tools/calibration mono cam2
3. tools/calibration stereo
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

Create dry-run calibration artifacts:

```bash
cd tools/calibration
uv run tennisbot-calibration target charuco --output ../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png --output-report ../../docs/calibration_charuco_target_sheet_YYYYMMDD.md
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Capture local calibration sessions:

```bash
cd tools/calibration
uv run tennisbot-calibration capture mono \
  --camera-id cam1 \
  --device /dev/video0 \
  --output ../../artifacts/calibration_sessions/cam1_session
uv run tennisbot-calibration capture stereo \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --left-device /dev/video0 \
  --right-device /dev/video2 \
  --output ../../artifacts/calibration_sessions/stereo_session \
  --prepare-uvc-controls
uv run tennisbot-calibration capture inspect \
  --session ../../artifacts/calibration_sessions/stereo_session \
  --output-report ../../docs/calibration_capture_quality_YYYYMMDD.md
uv run tennisbot-calibration capture detect-charuco \
  --session ../../artifacts/calibration_sessions/stereo_session \
  --output ../../artifacts/calibration_sessions/stereo_session/observations.json \
  --output-report ../../docs/calibration_charuco_detection_YYYYMMDD.md
uv run tennisbot-calibration calibrate mono \
  --observations ../../artifacts/calibration_sessions/cam1_session/observations.json \
  --output ../../artifacts/calibration/cam1 \
  --camera-id cam1
uv run tennisbot-calibration calibrate stereo \
  --observations ../../artifacts/calibration_sessions/stereo_session/observations.json \
  --left-mono ../../artifacts/calibration/cam1 \
  --right-mono ../../artifacts/calibration/cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2
```

Import existing CameraCalibLab calibration:

```bash
cd tools/calibration
uv run tennisbot-calibration package import-scanned-camera-calib-lab \
  --root ../../CameraCalibLab/runs/calibrations \
  --cam1-pattern dfoptix_charuco_auto_combined_rational_20260620_top_right_eps1e7 \
  --cam2-pattern dfoptix_charuco_auto_cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --limit 12 \
  --output-report ../../docs/calibration_candidate_scan_YYYYMMDD.md
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

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

Run calibration review GUI:

```bash
cd tools/calibration/frontend/review
bun test
bun run build
PORT=5188 bun run dev
```

## Current Verification Evidence

Most recent software verification:

```text
cd tools/calibration && uv run pytest -q
Result: 20 passing tests, 0 failures.

cd tools/calibration/frontend/review && bun test && bun run build
Result: 12 passing tests, build passed.

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
Calibration capture sessions: dry-run mono/stereo sessions wrote manifests,
frames, summary, and review files; a real 1-pair stereo hardware probe opened
/dev/video0 and /dev/video2 at 1280x720 MJPG. The capture tool can also apply
the local high-brightness UVC preset and inspect sessions before target
detection. The latest dry-run inspection accepted 4/4 images; the latest real
hardware probe rejected both images as low contrast / likely blank, so it is not
ready for mono/stereo solve. ChArUco detection is implemented for the DFOptix
14x9 `DICT_5X5_100` target profile; a rendered target dry-run detected 104
corners and 63 markers, while the current real hardware probe detected 0
corners in both views. Mono solve is implemented from accepted ChArUco
observations; the rendered/perspective-warped dry-run produced an accepted mono
package with RMS 3.551 px and package verification accepted. Stereo solve is
implemented from accepted stereo observations plus mono packages; the rendered
dry-run produced an accepted stereo package with stereo RMS 3.598 px, baseline
0.034805 m, and package verification accepted.
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
