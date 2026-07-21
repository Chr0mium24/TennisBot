# TennisBot Architecture Simplification Plan

Date: 2026-06-28

## Goal

Simplify TennisBot into a real-machine-first workspace. The system should run on
one development/control machine with real USB cameras, local YOLO inference,
local calibration artifacts, a 3D visualization frontend, and a small core
algorithm library.

The important product flow is:

```text
calibrate cameras -> load calibration + YOLO model -> view two USB cameras
-> detect tennis ball in both images -> triangulate 3D ball position
-> estimate trajectory -> show prediction curve in 3D
```

## Current Shape

The repository currently tracks several standalone child projects:

```text
TennisBot/
  CameraCalibLab/          camera calibration workspace
  TennisBallDetectorLab/   YOLO annotation, training, evaluation, export
  BallTrajectoryLab/       stereo geometry, 3D prediction, trajectory reports
  TennisWebSim/            browser simulation, ROSBridge, frontend workbench
  TennisBotCV/             legacy integration shell and shared references
```

This is workable for experimentation, but too broad for the next phase. YOLO
and calibration are tools that prepare artifacts. They should not be coupled to
the live runtime or treated as peer runtime applications.

## Target Shape

Use one repository, but keep tools and runtime packages isolated:

```text
TennisBot/
  apps/
    live3d/                real USB stereo camera + YOLO + 3D visualization
    sim/                   simulation frontend and real ROS/chassis adapter

  packages/
    core/                  coordinates, stereo geometry, tracking, prediction
    camera/                USB camera capture and frame-stream abstractions
    contracts/             shared schemas and TypeScript/Python data contracts

  tools/
    yolo/                  annotation, training, evaluation, model export
    calibration/           mono/stereo calibration, review UI, package export

  artifacts/               local generated outputs, ignored by git
    calibration/
    models/
    sessions/

  docs/
```

The target can still be implemented gradually using the existing child projects
as sources. The final boundary is more important than the first mechanical move.

## Ownership Boundaries

### `tools/yolo`

YOLO is an offline and runtime-support tool. It owns:

- dataset collection and annotation helpers;
- training and validation commands;
- model export to `.pt`, `.onnx`, or other runtime formats;
- evaluation reports;
- one canonical model-package format.

It does not own:

- stereo triangulation;
- trajectory prediction;
- frontend rendering;
- calibration capture or solving;
- simulation control logic.

The live runtime consumes only the exported model package.

### `tools/calibration`

Calibration is a camera-preparation tool. It owns:

- single-camera calibration for `cam1`;
- single-camera calibration for `cam2`;
- stereo calibration for `cam1 + cam2`;
- capture/review GUI for calibration sessions;
- calibration quality reports;
- runtime calibration package export.

It does not own:

- YOLO training or inference;
- ball tracking policy;
- trajectory prediction;
- simulation;
- live application UI beyond calibration/review tools.

The live runtime consumes only the exported calibration package.

### `packages/core`

Core is the runtime algorithm library. It owns:

- coordinate systems and transforms;
- camera projection and stereo triangulation;
- timestamped 2D detection pairing;
- 3D ball state estimation;
- velocity estimation;
- trajectory and landing prediction;
- runtime quality flags for tracking and prediction.

Core should not import training code, calibration GUI code, OpenCV UI code, or
frontend rendering code. It should accept plain data contracts and return plain
data contracts.

### `apps/live3d`

`live3d` is the first real-machine product surface. It owns:

- opening two real USB camera streams;
- showing both live camera images;
- loading one YOLO model package;
- loading one stereo calibration package;
- running YOLO on both images;
- drawing 2D detections on both camera views;
- triangulating matched detections through `packages/core`;
- showing the 3D ball point, recent trail, prediction curve, and predicted
  landing point.

It should not train YOLO or solve calibration. If the required artifacts are
missing, it should fail with clear artifact requirements.

### `apps/sim`

Simulation remains useful, but it should be separate from the real USB runtime.
It owns browser simulation, real ROS/chassis integration, and simulated scene control.
It can reuse `packages/core` and `packages/contracts`, but must not hide missing
real-camera or real-calibration behavior with local substitutes.

## Artifact Contracts

### YOLO Model Package

The live runtime should load a directory such as:

```text
artifacts/models/tennis_ball_yolo/
  package.json
  labels.json
  preprocessing.json
  postprocessing.json
  model.pt
  eval_report.md
  eval_metrics.json
```

Minimum runtime fields:

- model path;
- label names;
- input image size;
- confidence threshold default;
- preprocessing normalization;
- postprocessing/NMS settings;
- evaluation summary.

### Calibration Package

The live runtime should load a directory such as:

```text
artifacts/calibration/stereo_cam1_cam2/
  package.json
  cam1.json
  cam2.json
  stereo.json
  rectification.json
  calibration_opencv.yaml
  verification.json
  summary.md
```

Minimum runtime fields:

- image size for each camera;
- camera matrix and distortion for each camera;
- stereo rotation and translation;
- rectification/projection matrices if available;
- reprojection RMS and acceptance status;
- package version and source session.

## Main Operating Flow

### 1. Calibrate `cam1`

Run the calibration tool with one USB camera. Output a mono package:

```text
artifacts/calibration/cam1/
```

Acceptance gates:

- enough views;
- good coverage across center, edges, and corners;
- accepted RMS threshold;
- saved summary and verification report.

### 2. Calibrate `cam2`

Repeat the same mono flow for the second USB camera. Output:

```text
artifacts/calibration/cam2/
```

The two mono calibrations should use the same target definition and image
resolution as the intended live runtime.

### 3. Calibrate Stereo

Use both cameras and the accepted mono intrinsics to solve stereo extrinsics.
Output:

```text
artifacts/calibration/stereo_cam1_cam2/
```

Acceptance gates:

- enough synchronized or static stereo pairs;
- both images detect the calibration target;
- stereo reprojection/rectification checks pass;
- baseline and extrinsics look physically plausible.

### 4. Prepare One YOLO Model

Use `tools/yolo` to train or select one canonical tennis-ball model package.
The runtime should not choose between scattered YOLO copies in different
projects.

Output:

```text
artifacts/models/tennis_ball_yolo/
```

### 5. Launch `live3d`

The app loads:

```text
artifacts/calibration/stereo_cam1_cam2/
artifacts/models/tennis_ball_yolo/
```

Then it opens the two USB cameras and renders:

- left camera live image with YOLO ball overlay;
- right camera live image with YOLO ball overlay;
- current 3D ball point;
- recent 3D trail;
- predicted trajectory curve;
- predicted landing point;
- runtime status for camera, model, calibration, detection, triangulation, and
  prediction.

## Migration Plan

### Phase 0: Freeze Boundaries

- Treat this document as the target boundary.
- Do not add new board-specific runtime code.
- Do not add another YOLO inference path.
- Do not add another calibration workflow outside the calibration tool.

### Phase 1: Define Contracts

- Write model-package schema.
- Write calibration-package schema.
- Write detection, stereo observation, 3D state, and prediction contracts.
- Add small fixtures that `apps/live3d` can load without depending on tool
  internals.

### Phase 2: Consolidate Runtime Core

- Move or wrap `BallTrajectoryLab` geometry and prediction code under
  `packages/core`.
- Keep the API data-only and testable.
- Add tests for triangulation, projection, and prediction using fixture
  calibration data.

### Phase 3: Consolidate Live App

- Build `apps/live3d` as the real-machine entry point.
- Reuse the existing realtime stereo GUI behavior where practical.
- Make artifact paths explicit CLI/config options.
- Start with CPU/local YOLO inference before optimizing.

### Phase 4: Move Tools Without Coupling

- Move `CameraCalibLab` functionality under `tools/calibration` or keep it as an
  isolated package until the move is low risk.
- Move `TennisBallDetectorLab` functionality under `tools/yolo` or keep it as an
  isolated package until the move is low risk.
- Keep both tools independently runnable with `uv` and `bun` where applicable.

### Phase 5: Retire Legacy Shells

- Status 2026-06-29: `TennisBotCV` was removed from the main repository because
  the live runtime is now owned by `apps/live3d`, `packages/contracts`,
  `packages/core`, `tools/calibration`, and `tools/yolo`; simulation source still
  remains in `TennisWebSim` until it is migrated to `apps/sim`.
- Update README and docs to describe only the active structure.

## Non-Goals

- No board-side deployment service.
- No hidden local substitute for real stereo tracking validation.
- No duplicated YOLO service in simulation and live runtime.
- No calibration solver embedded directly inside `apps/live3d`.
- No runtime dependency on training datasets or calibration capture sessions.

## First Useful Milestone

The first complete milestone is:

```text
accepted stereo calibration package
+ accepted YOLO model package
+ live3d opens two USB cameras
+ YOLO detections visible on both views
+ matched ball becomes a 3D point
+ 3D trail and prediction curve render in the scene
```

This milestone proves the real-machine loop without mixing training,
calibration, and runtime application code.
