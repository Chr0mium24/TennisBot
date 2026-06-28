# Simulation And Legacy Runtime Audit

Date: 2026-06-28

Branch: `refactor/sim-runtime-audit`

Scope: audit-only report for Agent E. Source directories were read as reference
only: `TennisWebSim/**`, `TennisBotCV/**`, and `BallTrajectoryLab/**`.

## Executive Summary

`apps/sim` should be the new home for the active TennisWebSim browser simulator,
ROSBridge client, Gazebo/Omni3 launch helpers, and simulation-only YOLO frame
upload experiments. It must stay separate from `apps/live3d` and must continue
to require ROS/Gazebo for any claim about a real catch loop.

`packages/core` should absorb plain geometry, stereo pairing, 3D state
estimation, and projectile prediction from `BallTrajectoryLab`, plus the
simulation-side pure math currently embedded in `TennisWebSim/apps/tennisweb`.
Core should not inherit UI rendering, report generation, ROSBridge, YOLO
runtime service code, or dataset/session readers.

`packages/contracts` should replace duplicated TypeScript contracts in
`TennisWebSim/packages/tennis-contracts` and should also become the canonical
shape for the Python detection/state/prediction dataclasses in
`BallTrajectoryLab`. The older `TennisBotCV/packages/tennis-contracts` copy was
retired with the `TennisBotCV` submodule.

`TennisBotCV` was retired from the main repository on 2026-06-29. It mostly
duplicated split-out projects or contained generated/runtime board artifacts.

## Current Runtime Inventory

### TennisWebSim

Keep as source for `apps/sim`:

- `TennisWebSim/apps/tennisweb`: active React/Three simulation workbench.
- `TennisWebSim/packages/tennis-scene`: reusable tennis court, robot, camera,
  and actor rendering.
- `TennisWebSim/packages/tennis-ros`: ROSBridge adapter around `roslib`,
  `/omni3_pose`, `/robot_pose`, and `/omni3_api/target`.
- `TennisWebSim/Tennis_Robot_Chassis`: ROS2/Gazebo workspace for the Omni3
  model, Gazebo bringup, controller, and tennis court world.
- `TennisWebSim/apps/tennisweb/scripts/set_ros_env.bash` and
  `start-gazebo-headless.bash`: simulation launch support that belongs with
  `apps/sim`.
- `TennisWebSim/apps/tennisweb/src/vision/*`: simulation vision modes. These
  should remain simulation-specific until their plain data contracts are
  promoted.

Do not treat as live runtime:

- `truth-noisy` and `replay-report` vision modes. They are valuable for
  simulation analysis but are local substitutes, not real camera validation.
- `backend-yolo` frame upload from simulated/video frames. It can remain a sim
  experiment, but `apps/live3d` should not depend on this HTTP/WebSocket service
  as its canonical real-machine path.
- Headless YOLO experiment scripts under `TennisWebSim/scripts`. Keep them with
  simulation/reporting unless a later tooling branch explicitly converts them to
  test fixtures.

### BallTrajectoryLab

Move or port to `packages/core`:

- `src/ball_trajectory_lab/stereo_geometry.py`: epipolar error, disparity,
  triangulation, reprojection error.
- `src/ball_trajectory_lab/stereo_fusion.py`: rectified stereo detection pairing
  policy.
- `src/ball_trajectory_lab/state_estimator_3d.py`: Kalman state estimator for
  3D ball state.
- `src/ball_trajectory_lab/predictor_3d.py`: projectile prediction and landing
  point.
- The plain concepts in `stereo_types.py` and `types.py`, after aligning field
  names with `packages/contracts`.

Keep out of `packages/core`:

- `stereo_render.py`: OpenCV/UI overlay rendering.
- `stereo_datasets.py`: dataset/session loading, unless refactored as a test
  fixture adapter outside core.
- `stereo_calib.py`: calibration package loading can be a thin artifact adapter,
  but calibration solving/export remains owned by `tools/calibration`.
- `scripts/generate_trajectory_html.py`: report generation belongs in a tool or
  archived experiment path, not runtime core.
- `stereo_eval_geometry.py`: keep as test/reference material or migrate only the
  pure formulas that are not duplicated by `stereo_geometry.py`.

### TennisBotCV

Retired from the main repository on 2026-06-29:

- `TennisBotCV/packages/tennis-contracts`: duplicate of the simulation contracts
  package, with drift in `src/types.ts`.
- `TennisBotCV/web/app`: a local service workbench that primarily starts
  TennisWebSim services from `/home/cr/Codes/TennisBot/TennisWebSim/apps/tennisweb`.
  This becomes redundant once `apps/sim` owns its own launch/dev workflow.
- `TennisBotCV/web/app/dist` and `TennisBotCV/web/app/tsconfig.tsbuildinfo`:
  generated frontend artifacts.
- `TennisBotCV/dist/board_web_rk3576*`: generated board deployment bundle that is
  no longer part of this main repository.
- `TennisBotCV/runs`, `captures`, `data/raw`, and `experiments`: historical
  local outputs. These should not survive as source-controlled runtime content.
- `TennisBotCV/kernel_work`: RK3576 kernel and boot image work. This is outside
  the simplified live3d/sim/core/contracts architecture and should be archived
  or owned by a hardware bringup repository if still needed.
- `TennisBotCV/yolov8n.pt`: loose model file. Replace with the canonical
  `artifacts/models/tennis_ball_yolo/` model package contract.

Historical references noted before deletion:

- `TennisBotCV/docs/*`: useful historical split documentation. Promote still
  relevant decisions into top-level `docs/`, then archive the rest.
- `TennisBotCV/references/*`: research references should move to top-level
  docs/references or an archive if still cited.
- Board camera preview/recording behavior in `dist/board_web_rk3576` is no
  longer part of this main repository. Any future board-console work should live
  in a separate owner instead of returning to the active TennisBot runtime tree.

## Target Ownership

### `apps/sim`

Own:

- Browser simulation UI currently in `TennisWebSim/apps/tennisweb`.
- Gazebo/ROSBridge integration and launch helpers.
- Omni3 simulation assets and control topics.
- Simulation-only camera projections, truth/noise modes, replay modes, and
  experiment harnesses.
- Static board/simulator embed only if still needed as a sim artifact.

Do not own:

- USB camera capture for the real machine.
- YOLO training or model export.
- Canonical live YOLO inference runtime.
- Calibration solving or package export.
- Any local robot chase/catch substitute that bypasses ROS/Gazebo.

### `packages/core`

Own:

- Projection, rectified stereo triangulation, disparity, epipolar/reprojection
  metrics.
- Detection pairing and timestamp matching.
- 3D ball observation/state estimation.
- Projectile prediction, trajectory samples, landing point, and quality flags.
- Pure math currently duplicated between BallTrajectoryLab and TennisWebSim.

Do not own:

- React/Three rendering.
- ROSBridge.
- FastAPI services.
- Ultralytics model loading.
- Calibration capture/solve UI.
- Dataset, run, or report file formats beyond explicit test fixtures.

### `packages/contracts`

Own canonical schemas for:

- Camera intrinsics/extrinsics and stereo calibration packages.
- YOLO model package metadata.
- 2D detection, detection frame, stereo pair, triangulated 3D point, tracked
  state, prediction curve, and landing point.
- Simulation telemetry only where it is shared across app boundaries.
- ROS/Gazebo topic constants if `apps/sim` and shared scene packages both need
  them.

The TypeScript and Python shapes should be generated from, or at least checked
against, the same schema source to avoid the current drift.

### Retired Legacy Content

Retire or archive:

- `TennisBotCV` was removed from the main repository on 2026-06-29.
- Generated frontend builds and Python cache/build outputs inside child
  projects.
- Loose model files and historical run outputs that are not part of the
  canonical artifact contracts.
- Duplicate project inventories after their decisions are promoted to top-level
  docs.

## Duplicate YOLO And Runtime Paths

### YOLO Duplicates

1. `TennisWebSim/apps/vision-yolo-service`
   - FastAPI service with optional `ultralytics` dependency.
   - Loads a loose path from `TENNIS_YOLO_MODEL`.
   - Defines its own Pydantic `Detection`, `DetectionFrame`, and `YoloConfig`.
   - Broadcasts detections over WebSocket for TennisWeb.

2. `TennisWebSim/apps/tennisweb/src/vision/*`
   - Defines matching TypeScript `Detection` and `DetectionFrame` types.
   - Uploads frames to `/vision/frame`.
   - Has `backend-yolo`, `truth-noisy`, and `replay-report` modes.

3. `TennisWebSim/apps/tennisweb/src/utils/tracking.ts`
   - Creates `SimulatedYoloDetection`.
   - Performs local projection and triangulation of simulated detections.

4. `TennisWebSim/scripts/run-headless-experiment.ts`
   - Spawns or targets the YOLO service and exports detection-frame reports.

5. `TennisBotCV/yolov8n.pt`
   - Loose model artifact outside the target model package.

6. Future `tools/yolo`
   - Should become the only owner of training/evaluation/export and the only
     producer of the model package consumed by live runtime.

Recommendation:

- Keep `TennisWebSim/apps/vision-yolo-service` as a simulation-only adapter until
  `apps/sim` is moved, then either retire it or rewire it to consume the same
  model package contract as `apps/live3d`.
- Do not create a second live YOLO service. `apps/live3d` should load the
  canonical model package directly or through a single runtime adapter owned by
  the live app/camera boundary.
- Promote `DetectionFrame` and `YoloConfig` into `packages/contracts`; delete the
  local Pydantic/TypeScript schema duplicates after both sides consume the
  contract.

### Former Runtime Duplicates

1. `TennisWebSim/packages/tennis-contracts` and
   `TennisBotCV/packages/tennis-contracts`
   - Same package intent, but `types.ts` has drift. TennisWebSim includes newer
     stereo calibration bias/residual telemetry fields.

2. `TennisWebSim/apps/tennisweb/src/utils/tracking.ts` and
   `BallTrajectoryLab/src/ball_trajectory_lab/stereo_geometry.py`
   - Both own projection/triangulation concepts. TennisWebSim version is
     Three.js/simulation-coupled; BallTrajectoryLab version is closer to a core
     runtime library.

3. `TennisWebSim/apps/tennisweb/src/utils/physics.ts` and
   `BallTrajectoryLab/src/ball_trajectory_lab/predictor_3d.py`
   - Both implement projectile/landing prediction with different coordinate
     conventions and constraints.

4. `TennisBotCV/web/app` and `TennisWebSim/apps/tennisweb`
   - TennisBotCV only wraps and launches the real simulation app. The wrapper is
     redundant after `apps/sim` owns launch/status commands.

5. `TennisBotCV/dist/board_web_rk3576/static/tennisweb` and
   `TennisWebSim/apps/board-embed`
   - Generated/embed simulation UI paths overlap. Keep one generated artifact
     pipeline, not source/runtime copies in both places.

## TennisBotCV Retirement Result

Removed from the main repository on 2026-06-29:

- `TennisBotCV/packages/tennis-contracts`; `packages/contracts` is now the active
  contract package.
- `TennisBotCV/web/app`; simulation source remains in `TennisWebSim` until an
  `apps/sim` migration is done.
- `TennisBotCV/yolov8n.pt`; the active model is the ignored runtime package under
  `artifacts/models/tennis_ball_yolo/`.
- Historical `runs`, `captures`, `data/raw`, and `experiments`.
- Generated web/app build outputs and caches.
- `TennisBotCV/dist/board_web_rk3576*` and `TennisBotCV/kernel_work`; board
  deployment and hardware bringup are no longer active responsibilities of this
  main repository.

Keep as migrated documentation or references:

- Split-plan and registry docs until their still-current decisions are promoted
  into top-level `docs`.
- Research PDFs/references if cited by current trajectory/prediction decisions.

## Suggested Wave 2 Order

1. Land contracts/core skeleton first.
2. Move or wrap BallTrajectoryLab pure geometry/prediction into
   `packages/core`.
3. Move TennisWebSim active app and ROS/Gazebo packages into `apps/sim`, keeping
   sim-only substitutes labeled as simulation.
4. Rewire `apps/sim` to consume `packages/contracts` and `packages/core` where
   practical.
5. Build/verify `apps/live3d` against canonical model/calibration packages.
6. Completed 2026-06-29: retire TennisBotCV duplicates and loose/generated
   artifacts from the main repository.

## Original Audit Verification

Audit commands from the original 2026-06-28 report:

```bash
git status --short --branch
sed -n '1,240p' docs/multi_agent_refactor_tasks_20260628.md
sed -n '1,620p' docs/architecture_simplification_plan_20260628.md
rg --files TennisWebSim TennisBotCV BallTrajectoryLab
rg -n "YOLO|yolo|ultralytics|detect|prediction|trajectory|triang|stereo|ROS|rosbridge|Gazebo|gazebo" TennisWebSim TennisBotCV BallTrajectoryLab --glob '!**/.git/**' --glob '!**/.venv/**' --glob '!**/node_modules/**' --glob '!**/kernel_work/**'
diff -qr TennisWebSim/packages/tennis-contracts TennisBotCV/packages/tennis-contracts || true
find TennisWebSim TennisBotCV BallTrajectoryLab -path '*/.git' -prune -o -path '*/.venv' -prune -o -path '*/node_modules' -prune -o -iname '*yolo*' -print | sort
```

Observed results:

- The only contract-package diff reported by `diff -qr` was
  `src/types.ts`.
- YOLO/runtime paths found include `TennisWebSim/apps/vision-yolo-service`,
  `TennisWebSim/apps/tennisweb/src/vision/*`,
  `TennisWebSim/scripts/run-headless-experiment.ts`, and
  `TennisBotCV/yolov8n.pt`.
- Existing dirty workspace entry `TennisBallDetectorLab` was present before this
  branch and was not touched.

This branch intentionally performs no build or test run because it is a
documentation-only audit and source directories are read-only for Agent E.
