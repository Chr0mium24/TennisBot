# Deletion Scope

Date: 2026-06-29

This document records the agreed cleanup scope before any destructive file
removal. The target project should keep only:

- YOLO annotation frontend and backend;
- simulation frontend and backend;
- the original local OpenCV calibration GUI.

## Delete

### New calibration tool and web review UI

Remove the new calibration tool package because calibration should use the
original `CameraCalibLab` OpenCV GUI only.

- `tools/calibration/`
- references to `tennisbot-calibration`
- references to `tools/calibration/frontend/review`
- references to the deleted Calibration Web GUI service
- docs created for the new calibration review GUI, command bridge, physical
  gate panels, target print-check workflow, and local runtime launcher if they
  only describe the deleted tool

### Live3D standalone app

Remove the standalone Live3D app because it overlaps with the simulation
visualization surface and is not implemented with Three.js. Future real-camera
visualization should be folded into the simulation app or shared Three.js scene
packages if needed.

- `apps/live3d/`
- references to `@tennisbot/live3d`
- references to the Live3D URL `http://127.0.0.1:5178/`
- runtime launcher, preflight, and runtime validation entries that only start or
  validate `apps/live3d`
- docs under `docs/` that describe Live3D waves, Live3D artifacts, Live3D ONNX
  backend, Live3D USB cameras, or Live3D runtime 3D

### Board-side code

Remove board-side product code and board-only build outputs. The local project
should no longer carry board appliance pages, ADB/SSH workflows, board service
management, or board embed builds.

- `TennisWebSim/apps/board-embed/`
- `TennisWebSim/dist/board-embed/`
- `CameraCalibLab/legacy/board_frontend_public/`
- `CameraCalibLab/legacy/board_frontend_src/`
- `CameraCalibLab/legacy/board_static/`
- board-specific package scripts in `TennisWebSim/package.json`
- board-specific workspace entries in `TennisWebSim/package.json`
- board-specific lockfile entries in `TennisWebSim/bun.lock`
- docs that describe board ADB, SSH, systemd, board web pages, board service
  management, RK board deployment, or board embed migration

### Simulation YOLO service backend

Remove the separate simulation YOLO backend service because the retained YOLO
backend should be the annotator backend only.

- `TennisWebSim/apps/vision-yolo-service/`
- `TennisWebSim/package.json` scripts:
  - `dev:yolo-service`
  - `test:yolo-service`
- simulation code paths that upload frames to `vision-yolo-service`, if they
  are only for that deleted backend
- docs that instruct running `uv run tennis-vision-yolo`

### New YOLO runtime package tool

Delete this only if the final retained YOLO surface is strictly the original
`TennisBallDetectorLab` annotator/training workspace.

- `tools/yolo/`
- references to `tennisbot-yolo`

If runtime model packaging remains useful for the retained YOLO workflow, keep
this item out of the deletion commit.

## Keep

### YOLO annotation frontend and backend

- `TennisBallDetectorLab/web/yolo-annotator/`
- `TennisBallDetectorLab/yolo/scripts/serve_annotator.py`
- `uv run tbl annotate`
- dataset annotation, validation, training, evaluation, and package commands in
  `TennisBallDetectorLab` unless separately removed later

### Simulation frontend and backend

- `TennisWebSim/apps/tennisweb/`
- `TennisWebSim/packages/tennis-contracts/`
- `TennisWebSim/packages/tennis-scene/`
- `TennisWebSim/packages/tennis-ros/`
- `TennisWebSim/Tennis_Robot_Chassis/`, if it remains the ROS/Gazebo simulation
  backend used by `tennisweb`

### Original calibration GUI

- `CameraCalibLab/`
- `uv run camera-calib-lab capture passive-gui`
- `uv run camera-calib-lab capture charuco-auto-gui`
- `uv run camera-calib-lab capture stereo-charuco-auto-gui`
- `uv run camera-calib-lab capture phase-gui`
- the DFOptix ChArUco target profile:
  `charuco.board.dfoptix_14x9_square15mm_marker11_25mm`

## Cleanup After Deletion

- Remove deleted paths from workspace/package manifests.
- Remove deleted service scripts from local runtime launchers and status checks.
- Update README architecture sections so the remaining architecture is:
  YOLO annotation, simulation, and original OpenCV calibration.
- Run the retained checks:
  - `cd TennisBallDetectorLab && uv run pytest`
  - `cd TennisBallDetectorLab/web/yolo-annotator && bun run check`
  - `cd TennisWebSim && bun run typecheck`
  - `cd CameraCalibLab && uv run pytest -q`
