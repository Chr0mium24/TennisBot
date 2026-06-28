# Multi-Agent Refactor Wave 5 Calibration Tool Plan

Date: 2026-06-29

## Objective

Turn `tools/calibration` from documentation-only boundary into an independent
`uv` Python calibration tool surface that can support the first required
workflow:

```text
mono calibration artifact -> mono calibration artifact -> stereo calibration artifact
```

This wave must not move or edit `CameraCalibLab`. It uses `CameraCalibLab` only
as a read-only reference for command names, artifact shapes, and GUI workflow
intent.

## Branch

```text
refactor/calibration-tool-runtime
```

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/calibration-tool-runtime`
- Write scope:
  - `tools/calibration/**`
  - `docs/**`
- Read-only reference:
  - `CameraCalibLab/README.md`
  - `CameraCalibLab/pyproject.toml`
  - `CameraCalibLab/src/camera_calib_lab/app/**`
  - `CameraCalibLab/src/camera_calib_lab/commands/**`
  - `CameraCalibLab/src/camera_calib_lab/packaging/**`
  - `CameraCalibLab/tests/**`
- Do not edit:
  - `CameraCalibLab/**`
  - `TennisBallDetectorLab/**`
  - `BallTrajectoryLab/**`
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `apps/**`
  - `packages/**`
  - `.gitmodules`

## Required Implementation

Create a standalone Python package under `tools/calibration` using `uv`:

```text
tools/calibration/
  pyproject.toml
  src/tennisbot_calibration/
  tests/
```

The package should expose a console script:

```bash
uv run tennisbot-calibration --help
```

Add a conservative command surface for the sequential calibration workflow:

```bash
uv run tennisbot-calibration gui mono --camera-id cam1 --output artifacts/calibration/cam1 --dry-run
uv run tennisbot-calibration gui mono --camera-id cam2 --output artifacts/calibration/cam2 --dry-run
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --output artifacts/calibration/stereo_cam1_cam2 --dry-run
uv run tennisbot-calibration package verify --path artifacts/calibration/stereo_cam1_cam2
```

Dry-run GUI commands should create reviewable local HTML files and deterministic
artifact JSON packages. They are allowed to be fixture/demo outputs, but must be
clearly marked as dry-run/non-hardware evidence in summaries. They must not
claim real camera validation.

## Artifact Requirements

Mono dry-run output should write:

- `package.json`
- `camera.json`
- `verification.json`
- `calibration_opencv.yaml`
- `summary.md`
- a local GUI/review HTML file

Stereo dry-run output should write:

- `package.json`
- `cam1.json`
- `cam2.json`
- `stereo.json`
- `rectification.json`
- `verification.json`
- `calibration_opencv.yaml`
- `summary.md`
- a local GUI/review HTML file

The JSON files must satisfy the contracts in
`tools/calibration/artifact_contracts.md` and must be consumable by the
runtime loader shapes introduced in Wave 4.

## GUI Scope For This Wave

This wave does not need to open physical USB cameras. The dry-run GUI is an
offline/local review surface that proves:

- the user-visible mono/stereo workflow exists under `tools/calibration`;
- each stage writes the correct artifact directory structure;
- generated summaries warn that hardware capture/solve is still pending;
- later real OpenCV capture can replace the dry-run frame source without
  changing the artifact contracts.

Real camera capture and OpenCV solving remain a later calibration wave.

## Tests

Add focused tests for:

- CLI help exposes `gui mono`, `gui stereo`, and `package verify`;
- mono dry-run writes the required package files for `cam1`;
- stereo dry-run writes the required package files for `cam1 + cam2`;
- `package verify` accepts generated dry-run mono/stereo packages;
- `package verify` rejects a package whose accepted flag is false or whose
  required file is missing;
- generated stereo `rectification.json` uses row-major nested matrices and
  matching camera IDs.

## Required Verification

The worker must run:

```bash
cd tools/calibration
uv sync
uv run pytest -q
uv run tennisbot-calibration --help
uv run tennisbot-calibration gui mono --camera-id cam1 --output ../../artifacts/calibration/cam1 --dry-run
uv run tennisbot-calibration gui mono --camera-id cam2 --output ../../artifacts/calibration/cam2 --dry-run
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --output ../../artifacts/calibration/stereo_cam1_cam2 --dry-run
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
git diff --check
git diff --name-only main..HEAD
```

Generated `artifacts/**` outputs must remain ignored or be deleted before
commit.

## Acceptance Criteria

- `tools/calibration` is an installable/testable `uv` Python project.
- The command surface supports the planned sequential mono/mono/stereo flow.
- Dry-run GUI output is local and reviewable, but explicitly not real hardware
  validation.
- Artifact packages match the documented runtime contract.
- `CameraCalibLab` remains untouched.
- No edits occur outside `tools/calibration/**` and `docs/**`.
- Existing `TennisBallDetectorLab` dirty state remains untouched.

## Lead Review Notes

The lead should check:

- artifact JSON field names match `artifact_contracts.md`;
- generated dry-run summaries cannot be mistaken for real calibration evidence;
- package verification catches missing required files and rejected artifacts;
- no runtime app imports calibration tool internals;
- no generated artifact files are committed.
