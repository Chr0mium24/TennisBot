# TennisBot

Top-level integration repository for the TennisBot workspace.

This repository records the exact commits for the standalone projects that make
up the robot, vision, calibration, trajectory, and simulation stack. The child
directories remain independent git repositories and are tracked
here as submodules/gitlinks.

## Projects

| Project | Purpose |
| --- | --- |
| `CameraCalibLab` | Camera calibration, capture, simulation, comparison, and runtime package export |
| `TennisBallDetectorLab` | YOLO annotation, dataset validation, training, evaluation, RKNN/export, and detector package handoff |
| `BallTrajectoryLab` | Stereo trajectory reconstruction, landing prediction, and trajectory reports |
| `TennisWebSim` | Browser simulation, ROSBridge integration, YOLO service, and vendored Omni3 ROS workspace |
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

## Architecture

- [Architecture simplification plan](docs/architecture_simplification_plan_20260628.md)
- [Multi-agent refactor task plan](docs/multi_agent_refactor_tasks_20260628.md)
- [Multi-agent refactor Wave 1 result](docs/multi_agent_refactor_wave1_result_20260628.md)
- [Multi-agent refactor Wave 2 core migration plan](docs/multi_agent_refactor_wave2_core_migration_plan_20260628.md)
- [Multi-agent refactor Wave 2 core migration result](docs/multi_agent_refactor_wave2_core_migration_result_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture plan](docs/multi_agent_refactor_wave3_live3d_core_fixture_plan_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture result](docs/multi_agent_refactor_wave3_live3d_core_fixture_result_20260628.md)
- [Multi-agent refactor Wave 3 Live3D core fixture review](docs/multi_agent_refactor_wave3_live3d_core_fixture_review_20260628.md)
- [Multi-agent refactor Wave 4 artifact loaders plan](docs/multi_agent_refactor_wave4_artifact_loaders_plan_20260628.md)

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

All tracked projects use GitHub remotes under `Chr0mium24`. `TennisWebSim`
also contains the upstream `Tennis_Robot_Chassis` submodule.
