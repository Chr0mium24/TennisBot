# TennisBot Current Architecture

Date: 2026-06-29

## Current Shape

TennisBot is a local-machine-first workspace. The active tracked code lives in
top-level `apps/`, `packages/`, `tools/`, and `scripts/`.

```text
TennisBot/
  apps/
    live3d/          browser USB stereo camera runtime, YOLO, 3D UI
  packages/
    contracts/       shared TypeScript data contracts
    core/            artifact loaders, stereo pairing, triangulation, prediction
  tools/
    calibration/     fixed DFOptix ChArUco OpenCV capture GUI
    yolo/            annotation, YOLO package, pure detection GUI
  scripts/
    live3d.ts        single root launcher/status check for Live3D
  artifacts/         ignored local runtime artifacts
  docs/
    current/         current operational truth
    reports/         business/report artifacts
    archive/         dated plans, probes, reviews, and historical results
```

Ignored legacy lab code can still exist under local `desperate/` directories,
but it is no longer the main tracked architecture.

## Tool Boundaries

### `tools/calibration`

Owns the mainline OpenCV calibration capture GUI for this project target:

- fixed DFOptix ChArUco target profile
  `dfoptix_charuco_14x9_square15mm_marker11_25mm`;
- `DICT_5X5_100`, 14 x 9 squares, 15 mm squares, 11.25 mm markers;
- mono capture GUI command;
- stereo capture GUI command;
- mono ChArUco solve and runtime package export;
- stereo ChArUco solve and runtime package export;
- USB camera brightness checks;
- capture quality checks for full-corner coverage, brightness, sharpness,
  stability, position buckets, and dwell capture;
- `session.json` capture sessions with saved frame paths plus per-frame
  metadata and summary artifacts.

Current commands:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

### `tools/yolo`

Owns tennis-ball detector tooling:

- local annotation frontend/backend via `tennisbot-yolo annotate`;
- runtime model package create/verify;
- pure OpenCV YOLO detection GUI via `tennisbot-yolo detect-gui`.

It does not own stereo geometry, calibration, camera/world transforms, Live3D
state, or trajectory prediction.

Current commands:

```bash
cd tools/yolo
uv run tennisbot-yolo annotate
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
uv run --extra detect tennisbot-yolo detect-gui --devices /dev/video0,/dev/video2 --model ../../artifacts/models/tennis_ball_yolo/model.pt --tile
```

### `packages/core`

Owns pure runtime algorithms and artifact validation:

- YOLO and stereo calibration artifact metadata loaders;
- stereo detection pairing;
- rectified stereo triangulation;
- projectile trajectory prediction.

It has no browser UI, OpenCV GUI, camera device access, dataset management, or
training code.

### `apps/live3d`

Owns the real-machine browser runtime:

- opens two browser USB camera streams;
- loads YOLO and calibration artifacts from `/artifacts/...`;
- runs browser ONNX YOLO inference when a compatible package is present;
- overlays detections;
- feeds left/right detections to `packages/core`;
- renders the camera-frame 3D point, trail, prediction curve, and landing point;
- exposes `window.__tennisbotLive3dSnapshot` for local runtime inspection.

Current limitation: Live3D can load stereo calibration artifacts, but it does
not know the physical camera pose relative to a tennis court. Its 3D output
should be treated as camera-frame geometry until a court/world transform is
measured and applied.

## Runtime Flow

```text
1. tools/calibration captures mono/stereo ChArUco sessions
2. tools/calibration solves mono/stereo calibration packages under artifacts/calibration/...
3. tools/yolo creates or verifies artifacts/models/tennis_ball_yolo
4. apps/live3d loads the YOLO and calibration artifacts
5. the operator starts two USB cameras in the browser
6. Live3D runs YOLO on left/right frames
7. packages/core pairs detections, triangulates a 3D point, and predicts motion
8. Live3D renders detections, 3D trail, prediction curve, and readiness gates
```

## Current Validation State

The latest known imported stereo package is accepted by the artifact verifier,
but it has a review warning:

```text
stereo_rms_px=0.423652
epipolar_rms_px=4.330
runtime review threshold=2.000
baseline_m=0.052486
```

This means the package is usable for continued local experiments, but it should
not be treated as final physical acceptance. Recalibrate with the real mounted
camera geometry before relying on far-distance depth.

Live3D exposes browser readiness gates for local operation.

## Main Commands

Camera brightness sanity check:

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
bun scripts/calib.ts preview
```

Start the local browser runtime:

```bash
bun scripts/live3d.ts
bun scripts/live3d.ts --status
```

Verify core packages:

```bash
cd packages/contracts && bun test && bun run typecheck
cd packages/core && bun test && bun run typecheck
```

Verify Live3D:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build
```

## Remaining Engineering Work

- Recalibrate after the cameras are mounted in their real physical positions.
- Apply or document the browser-frame scaling, rectification, and camera/world
  transform rules before claiming court-coordinate 3D correctness.
- Run Live3D with a visible tennis ball and observe the browser readiness gates
  through `prediction-ready`.
