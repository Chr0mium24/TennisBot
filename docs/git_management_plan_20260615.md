# Git management plan

Date: 2026-06-15

## Goal

Create a top-level integration repository for `/home/cr/Codes/TennisBot` that
tracks each standalone project by commit while keeping the projects independent.

## Chosen Structure

Use a superproject/submodule layout:

```text
TennisBot/
  CameraCalibLab/
  TennisBallDetectorLab/
  BallTrajectoryLab/
  BoardCameraConsole/
  TennisWebSim/
  TennisBotCV/
```

Each child directory remains its own git repository. The top-level repository
stores the child commit ids as gitlinks.

## Remote Decisions

- `CameraCalibLab`: keep `https://github.com/Chr0mium24/CameraCalibLab.git`.
- `TennisBotCV`: keep `https://github.com/Chr0mium24/TennisBotCV.git`.
- `TennisBallDetectorLab`, `BoardCameraConsole`, `BallTrajectoryLab`, and
  `TennisWebSim`: use local submodule URLs for now because no origin remote is
  configured yet.

## Verification Plan

1. Confirm child worktrees are clean.
2. Add `.gitmodules`, top-level README, and docs.
3. Add child repositories as gitlinks.
4. Commit the top-level repository.
5. Confirm `git submodule status` records all expected child commits.

## Result

Completed.

- Initialized `/home/cr/Codes/TennisBot` as a top-level `main` branch git
  repository.
- Added `.gitmodules` and tracked each standalone project as a gitlink:

  ```text
  CameraCalibLab          178a8626ad896f951857d3d670dc153c5a03dcaf
  TennisBallDetectorLab   b57c95880c382fdaf657d1b50e3f989e12d38712
  BoardCameraConsole      3cbfdf2b2df1c81e353cfc1cec812a2373dda64b
  BallTrajectoryLab       40669113a4d822369b74f88835f76bf84a717b3f
  TennisBotCV             73e08dc8722afa57a366ca555a79510e5786bc3b
  TennisWebSim            972a13eb5e9f6a277e6685c7f00fe06e9a77fda9
  ```

- Added a top-level README with project roles and the intended workflow.
- Verified that each child project worktree is clean.

## Remaining Follow-up

Create real remotes for the local-only projects and replace their local
submodule URLs:

- `TennisBallDetectorLab`
- `BoardCameraConsole`
- `BallTrajectoryLab`
- `TennisWebSim`
