# TennisBot

Top-level integration repository for the TennisBot workspace.

This repository records the exact commits for the standalone projects that make
up the robot, vision, calibration, trajectory, board-console, and simulation
stack. The child directories remain independent git repositories and are tracked
here as submodules/gitlinks.

## Projects

| Project | Purpose |
| --- | --- |
| `CameraCalibLab` | Camera calibration, capture, simulation, comparison, and runtime package export |
| `TennisBallDetectorLab` | YOLO annotation, dataset validation, training, evaluation, RKNN/export, and detector package handoff |
| `BallTrajectoryLab` | Stereo trajectory reconstruction, landing prediction, and trajectory reports |
| `BoardCameraConsole` | Board-side camera preview, recording, file management, services, and deployment helpers |
| `TennisWebSim` | Browser simulation, ROSBridge integration, board embed, YOLO service, and vendored Omni3 ROS workspace |
| `TennisBotCV` | Lightweight integration shell and shared contracts |

## Common Commands

Run the full WebSim + ROS/Gazebo helper:

```bash
cd TennisWebSim/apps/tennisweb
bun run dev:all
```

Run the YOLO annotator:

```bash
cd TennisBallDetectorLab
uv run tbl annotate
```

Run calibration tools:

```bash
cd CameraCalibLab
uv run camera-calib-lab --help
```

## Git Workflow

Work inside a child project when changing its code, commit there first, then
come back to this top-level repository and commit the updated submodule pointer.

```bash
git -C TennisWebSim status
git -C TennisWebSim commit -am "..."
git add TennisWebSim
git commit -m "Update TennisWebSim pointer"
```

The top-level repository should only contain integration docs, `.gitmodules`,
and submodule pointers.

## Remote Status

`CameraCalibLab` and `TennisBotCV` already use GitHub remotes. The other local
projects currently use local submodule URLs and should get real remotes before
this top-level repository is shared across machines.

