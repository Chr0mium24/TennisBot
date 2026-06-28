# TennisBot Final Runtime Validation

Date: 2026-06-29

## Scope

This validation covers the current local-machine software architecture:

- `packages/contracts`
- `packages/core`
- `tools/calibration`
- `tools/yolo`
- `apps/live3d`

It does not claim physical validation with real USB cameras, a real exported
ONNX tennis-ball model, a real stereo calibration package, or ROS/Gazebo catch
control.

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
```

Result: 38 tests passed, typecheck passed, browser bundle built.

Dev server smoke:

```bash
PORT=5178 bun ./scripts/serve.js
curl -I http://localhost:5178/
curl -I http://localhost:5178/assets/main.js
curl -I http://localhost:5178/artifacts/models/tennis_ball_yolo/package.json
curl -I http://localhost:5178/artifacts/calibration/stereo_cam1_cam2/package.json
```

Result: all HTTP checks returned `200 OK`.

### Calibration Tool

```bash
cd tools/calibration
uv run pytest -q
uv run tennisbot-calibration gui mono --camera-id cam1 --dry-run --output ../../artifacts/calibration/cam1
uv run tennisbot-calibration gui mono --camera-id cam2 --dry-run --output ../../artifacts/calibration/cam2
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --dry-run --output ../../artifacts/calibration/stereo_cam1_cam2
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

Result: 8 tests passed. Dry-run mono and stereo packages were written and the
stereo package verified with `accepted: true`, `dry_run: true`, and
`hardware_validated: false`.

### YOLO Tool

```bash
cd tools/yolo
uv run pytest -q
uv run tennisbot-yolo package create --dry-run --output-dir ../../artifacts/models/tennis_ball_yolo
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

Result: 12 tests passed. Dry-run YOLO package was written and verified.

## Current Evidence

- YOLO and calibration are separate standalone tool packages under `tools/`.
- Live3D consumes only model/calibration artifacts under `artifacts/`.
- Runtime core algorithms live under `packages/core`.
- Shared data contracts live under `packages/contracts`.
- Board-side runtime code is not part of the current active architecture.
- The only dirty worktree entry after validation is the pre-existing
  `TennisBallDetectorLab` submodule state, which remains untouched.

## Remaining Physical Validation

Before claiming full real-world operation:

1. Replace dry-run artifacts with real accepted calibration and ONNX model
   packages.
2. Run Live3D against two physical USB cameras.
3. Confirm browser ONNX detections on real camera frames.
4. Confirm stereo 3D point stability and prediction quality.
5. Validate ROS/Gazebo closed-loop catch behavior only after real visual
   tracking is stable.
