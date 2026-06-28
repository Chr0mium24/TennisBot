# Multi-Agent Refactor Wave 7 Live3D Artifacts Review

Date: 2026-06-29

## Reviewed Work

- Worker branch: `refactor/live3d-artifact-loader`
- Worker commit: `fc42137 Implement Live3D artifact loader`
- Lead review fix: `457736b Tighten Live3D artifact serving`
- Main merge commit: `dd9962c Merge Live3D artifact loading`

## Scope Review

Accepted scope:

- `apps/live3d/**`
- `docs/**`

No edits were made to:

- `packages/**`
- `tools/**`
- `TennisBallDetectorLab/**`
- `CameraCalibLab/**`
- `BallTrajectoryLab/**`
- `TennisWebSim/**`
- `TennisBotCV/**`
- `.gitmodules`

The pre-existing dirty `TennisBallDetectorLab` submodule state remained
untouched and unstaged.

## Review Findings

The worker implementation correctly added an app-local artifact adapter:

- browser `fetch` JSON reader;
- YOLO artifact package loading through `loadYoloModelArtifactMetadata`;
- stereo calibration artifact package loading through
  `loadStereoCalibrationArtifact`;
- explicit loaded/blocked status objects for ordinary missing or invalid
  artifact data;
- UI status cards for YOLO and stereo calibration artifacts.

The rendered 3D scene remains fixture-only and still states that it does not
validate real USB cameras, real YOLO inference, real calibration, or real
prediction.

Lead review tightened two issues before merge:

- `/artifacts/...` static serving now resolves real paths, serves files only,
  and rejects symlink escapes in addition to traversal attempts;
- artifact status text is HTML-escaped before insertion into `innerHTML`.

## Verification

Commands run after merge:

```bash
cd apps/live3d
bun test
bun run typecheck
bun run build

cd ../../packages/core
bun test
bun run typecheck
```

Results:

- `apps/live3d`: 9 tests passed; TypeScript passed; browser bundle built.
- `packages/core`: 21 tests passed; TypeScript passed.
- `git diff --check HEAD~5..HEAD`: passed with no output.

Lead smoke test:

```bash
cd tools/yolo
uv run tennisbot-yolo package create --output-dir ../../artifacts/models/tennis_ball_yolo --dry-run
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo

cd ../calibration
uv run tennisbot-calibration gui mono --camera-id cam1 --output ../../artifacts/calibration/cam1 --dry-run
uv run tennisbot-calibration gui mono --camera-id cam2 --output ../../artifacts/calibration/cam2 --dry-run
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --output ../../artifacts/calibration/stereo_cam1_cam2 --dry-run
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2

cd ../../apps/live3d
bun ./scripts/serve.js
```

HTTP checks while the server was running:

- `/artifacts/models/tennis_ball_yolo/package.json`: served JSON.
- `/artifacts/calibration/stereo_cam1_cam2/package.json`: served JSON.
- `/artifacts/../README.md`: returned `404`.

Generated `artifacts/**` smoke outputs were removed after verification.

## Remaining Work

This wave still does not open USB cameras or run YOLO inference. The next wave
should add real camera frame acquisition and a runtime inference adapter, while
continuing to treat YOLO and calibration as artifact-producing tools.
