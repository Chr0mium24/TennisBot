# Multi-Agent Refactor Task Plan

Date: 2026-06-28

## Objective

Use multiple Codex `gpt-5.5` medium-reasoning subagents to refactor TennisBot
toward the simplified architecture in
[`architecture_simplification_plan_20260628.md`](architecture_simplification_plan_20260628.md).

The lead agent owns review, merge order, conflict resolution, and final
verification. Worker agents own isolated branches with explicit write scopes.

## Current Constraint

`TennisBallDetectorLab` currently has many local uncommitted dataset and label
changes. Treat those as user-owned work. Do not revert, delete, move, or format
those files during the refactor.

YOLO refactor work in the first wave must avoid direct edits under:

```text
TennisBallDetectorLab/yolo/dataset/
TennisBallDetectorLab/yolo/runs/
TennisBallDetectorLab/yolo/models/
```

## Target Architecture

```text
TennisBot/
  apps/
    live3d/
    sim/

  packages/
    core/
    camera/
    contracts/

  tools/
    yolo/
    calibration/

  artifacts/
    calibration/
    models/
    sessions/

  docs/
```

## Branch Rules

- Each worker creates one branch from current `main`.
- Branch names use `refactor/<area>-<short-topic>`.
- Each branch commits its own changes.
- Workers must not merge into `main`.
- Workers must not rebase or reset shared branches.
- Workers must not revert changes they did not make.
- Workers must list changed files and verification commands in their final
  report.
- The lead agent reviews each branch before merge.

## Lead Review And Merge Rules

The lead agent must:

1. Inspect branch diff and changed file ownership.
2. Check for accidental edits to user-owned dirty files.
3. Run targeted verification for that branch.
4. Prefer merge order that minimizes conflicts.
5. Resolve conflicts manually when needed.
6. Commit the merge result.
7. Update this document or a follow-up result document if the plan changes.

No branch is accepted if it breaks the tool/runtime boundary:

- `tools/yolo` must not import calibration or trajectory internals.
- `tools/calibration` must not import YOLO training or live app code.
- `packages/core` must not import tool GUI, training, or frontend code.
- `apps/live3d` must consume artifacts and contracts, not tool internals.

## Wave 1: Parallel Preparation Branches

Wave 1 avoids heavy submodule moves. It creates the stable boundaries needed
before large file moves.

### Agent A: Contracts And Core Skeleton

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/contracts-core-skeleton`
- Write scope:
  - `packages/contracts/**`
  - `packages/core/**`
  - `docs/**` only if documenting contracts/core decisions
- Do not edit:
  - `CameraCalibLab/**`
  - `TennisBallDetectorLab/**`
  - `TennisWebSim/**`
  - `BallTrajectoryLab/**`

Tasks:

- Create initial data contracts for:
  - camera intrinsics;
  - stereo extrinsics;
  - YOLO 2D detection;
  - timestamped stereo detection pair;
  - triangulated 3D ball point;
  - prediction curve and landing point.
- Create a minimal core package skeleton for:
  - projection/triangulation API placeholder;
  - prediction API placeholder;
  - artifact loading interfaces.
- Add focused tests for contract shape and simple geometry placeholders.
- Keep implementation conservative and data-only.

Expected output:

- A committed branch with package skeleton and tests.
- Notes on which BallTrajectoryLab code should later migrate into
  `packages/core`.

### Agent B: Live3D Application Shell

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/live3d-shell`
- Write scope:
  - `apps/live3d/**`
  - `docs/**` only if documenting live app operation
- Do not edit:
  - existing subprojects;
  - top-level `.gitmodules`;
  - YOLO datasets.

Tasks:

- Create the first `apps/live3d` frontend/app shell.
- Define the intended UX:
  - two live USB camera panels;
  - 2D YOLO overlays;
  - 3D scene area;
  - status panel for camera/model/calibration/tracking/prediction.
- Add config placeholders for:
  - left/right camera device;
  - YOLO model package path;
  - stereo calibration package path.
- Add a static fixture mode only for UI development. It must be clearly labeled
  as fixture mode and must not claim real tracking validation.

Expected output:

- A committed branch with an app skeleton that can be built or typechecked.
- A short run command and verification result.

### Agent C: Calibration Tool Boundary

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/calibration-tool-boundary`
- Write scope:
  - `tools/calibration/**`
  - `docs/**`
- Read-only reference:
  - `CameraCalibLab/**`
- Do not move `CameraCalibLab` in Wave 1.

Tasks:

- Create `tools/calibration` as the future home for calibration tooling.
- Add a README that maps current `CameraCalibLab` commands to the target tool
  layout.
- Define the mono calibration and stereo calibration artifact contracts.
- Add a migration checklist for moving CameraCalibLab later.
- Keep the current working CameraCalibLab untouched.

Expected output:

- A committed branch with `tools/calibration` docs/contracts only.
- No behavior change to current calibration commands.

### Agent D: YOLO Tool Boundary

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/yolo-tool-boundary`
- Write scope:
  - `tools/yolo/**`
  - `docs/**`
- Read-only reference:
  - `TennisBallDetectorLab/README.md`
  - `TennisBallDetectorLab/src/**`
  - `TennisBallDetectorLab/web/**`
- Do not edit:
  - `TennisBallDetectorLab/yolo/dataset/**`
  - `TennisBallDetectorLab/yolo/runs/**`
  - `TennisBallDetectorLab/yolo/models/**`
  - current user-owned dirty YOLO files.

Tasks:

- Create `tools/yolo` as the future home for YOLO tooling.
- Add a README that maps current TennisBallDetectorLab commands to target tool
  commands.
- Define the model package contract consumed by `apps/live3d`.
- Add a migration checklist for moving TennisBallDetectorLab later.
- Do not touch dataset files or large model artifacts.

Expected output:

- A committed branch with `tools/yolo` docs/contracts only.
- Confirmation that dirty YOLO dataset files were not changed.

### Agent E: Simulation And Legacy Runtime Audit

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/sim-runtime-audit`
- Write scope:
  - `docs/**`
- Read-only reference:
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `BallTrajectoryLab/**`

Tasks:

- Audit what should become:
  - `apps/sim`;
  - `packages/core`;
  - `packages/contracts`;
  - retired legacy content.
- Identify duplicate YOLO/runtime paths.
- Identify which TennisBotCV pieces can be deleted after Live3D exists.
- Produce a merge-safe Markdown report only.

Expected output:

- A committed branch with a documentation report.
- No source code changes.

## Wave 1 Merge Order

Preferred merge order:

1. `refactor/contracts-core-skeleton`
2. `refactor/calibration-tool-boundary`
3. `refactor/yolo-tool-boundary`
4. `refactor/live3d-shell`
5. `refactor/sim-runtime-audit`

Reasoning:

- Contracts/core should land first so later branches can adapt to the canonical
  schemas.
- Tool boundary docs are low risk and should not conflict with app shell work.
- Live3D can be adjusted after contract names are final.
- Audit-only branch can merge last because it should not affect code.

## Wave 2: Structural Moves

Wave 2 starts only after Wave 1 lands.

Candidate branches:

- `refactor/move-calibration-tool`
  - move or vendor `CameraCalibLab` into `tools/calibration`;
  - preserve `uv` workflow;
  - update top-level docs.
- `refactor/move-yolo-tool`
  - move or vendor `TennisBallDetectorLab` into `tools/yolo`;
  - preserve dirty user data by excluding or explicitly carrying it only after
    user approval;
  - preserve `uv` and `bun` workflow.
- `refactor/move-sim-app`
  - move active TennisWebSim app code under `apps/sim`;
  - preserve ROS/Gazebo rules.
- `refactor/core-migration`
  - move selected BallTrajectoryLab runtime geometry/prediction into
    `packages/core`.
- `refactor/retire-tennisbotcv`
  - delete or archive TennisBotCV after active runtime paths exist.

Wave 2 branches should be mostly serial because they will touch `.gitmodules`,
top-level README, and large directory paths.

## Acceptance Gates For Final Architecture

The refactor is not complete until:

- `tools/yolo` can produce one model package.
- `tools/calibration` can produce one stereo calibration package.
- `apps/live3d` can load those two packages.
- `apps/live3d` can show two USB camera streams.
- YOLO detections render on both views.
- a matched detection becomes a 3D ball point through `packages/core`.
- the 3D scene shows point, trail, prediction curve, and landing point.
- simulation remains separate and does not masquerade as real hardware
  validation.

## Lead Agent Checklist Before Starting Workers

- Confirm current `main` commit.
- Confirm current dirty files and user-owned changes.
- Commit this task plan.
- Spawn the Wave 1 workers with explicit branch names and write scopes.
- Continue with non-overlapping review preparation while workers run.
