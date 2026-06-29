# Multi-Agent Refactor Wave 6 YOLO Tool Plan

Date: 2026-06-29

## Objective

Turn `tools/yolo` from documentation-only boundary into an independent `uv`
Python tool surface that can produce and verify the runtime model package
consumed by `apps/live3d`.

This wave must not train YOLO, run inference, move datasets, or edit
`TennisBallDetectorLab`. It uses `TennisBallDetectorLab` only as a read-only
reference for current handoff package behavior.

## Branch

```text
refactor/yolo-tool-runtime
```

## Worker Assignment

- Model: `gpt-5.5`
- Reasoning: `medium`
- Branch: `refactor/yolo-tool-runtime`
- Write scope:
  - `tools/yolo/**`
  - `docs/**`
- Read-only reference:
  - `TennisBallDetectorLab/README.md`
  - `TennisBallDetectorLab/src/tennis_ball_detector_lab/deliverable.py`
  - `TennisBallDetectorLab/src/tennis_ball_detector_lab/cli.py`
  - `TennisBallDetectorLab/tests/test_dataset_and_deliverable.py`
  - `packages/core/src/artifacts.test.ts`
  - `tools/yolo/MODEL_PACKAGE_CONTRACT.md`
- Do not edit:
  - `TennisBallDetectorLab/**`
  - `CameraCalibLab/**`
  - `BallTrajectoryLab/**`
  - `TennisWebSim/**`
  - `TennisBotCV/**`
  - `apps/**`
  - `packages/**`
  - `.gitmodules`

## Required Implementation

Create a standalone Python package under `tools/yolo` using `uv`:

```text
tools/yolo/
  pyproject.toml
  src/tennisbot_yolo/
  tests/
```

The package should expose a console script:

```bash
uv run tennisbot-yolo --help
```

Add a conservative command surface for model package creation and validation:

```bash
uv run tennisbot-yolo package create --output-dir artifacts/models/tennis_ball_yolo --model-onnx path/to/model.onnx --default-model onnx
uv run tennisbot-yolo package create --output-dir artifacts/models/tennis_ball_yolo --dry-run
uv run tennisbot-yolo package verify --path artifacts/models/tennis_ball_yolo
```

The dry-run package may include a tiny deterministic placeholder model file,
but it must be explicitly marked as non-inference/dry-run evidence in
`eval_report.md`, `eval_metrics.json`, and package metadata. It must not claim
real training or model accuracy.

## Runtime Package Requirements

`package create` should write:

- `package.json`
- `metadata.json` as a temporary compatibility alias for older handoff readers
- `labels.json`
- `preprocessing.json`
- `postprocessing.json`
- one or more model files when supplied or when `--dry-run` is used
- `eval_report.md`
- `eval_metrics.json`
- `package_manifest.json`

`package.json`, `labels.json`, `preprocessing.json`, and `postprocessing.json`
must match `tools/yolo/MODEL_PACKAGE_CONTRACT.md` and be consumable by the
Wave 4 runtime loader in `packages/core`.

Model entries must include:

- `path`
- `sha256`
- `bytes`
- `runtime`

Default model selection must be explicit and must reference an existing model
entry.

## Verification Requirements

`package verify` should reject:

- missing `package.json`;
- unsupported `contract`;
- missing class `0 = tennis_ball`;
- missing selected model entry;
- missing selected model file;
- mismatched model `sha256`;
- mismatched model `bytes`;
- out-of-range confidence threshold;
- malformed preprocessing input size.

## Tests

Add focused tests for:

- CLI help exposes `package create` and `package verify`;
- dry-run package writes all required files and marks itself non-inference;
- package creation from a supplied ONNX fixture records correct bytes and
  SHA-256;
- package verification accepts generated packages;
- package verification rejects missing selected model files;
- package verification rejects checksum mismatch;
- package verification rejects labels without class `0 = tennis_ball`;
- generated package metadata is shaped for the Wave 4 runtime loader.

## Required Verification

The worker must run:

```bash
cd tools/yolo
uv sync
uv run pytest -q
uv run tennisbot-yolo --help
uv run tennisbot-yolo package create --output-dir ../../artifacts/models/tennis_ball_yolo --dry-run
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
git diff --check
git diff --name-only main..HEAD
```

Generated `artifacts/**` outputs must remain ignored or be deleted before
commit. No real `.pt`, `.onnx`, `.rknn`, datasets, or training runs should be
committed.

## Acceptance Criteria

- `tools/yolo` is an installable/testable `uv` Python project.
- The command surface supports runtime package creation and verification.
- Generated package metadata satisfies `MODEL_PACKAGE_CONTRACT.md`.
- Dry-run output cannot be mistaken for trained or inference-ready evidence.
- `TennisBallDetectorLab` remains untouched.
- No edits occur outside `tools/yolo/**` and `docs/**`.
- Existing `TennisBallDetectorLab` dirty state remains untouched.

## Lead Review Notes

The lead should check:

- `package.json` uses the new canonical contract, not only legacy
  `metadata.json`;
- class `0 = tennis_ball` is enforced;
- selected model file existence, bytes, and SHA-256 are verified;
- no training, inference, or dataset scanning is introduced;
- generated dry-run model files are not committed;
- the package can be loaded by `packages/core` artifact metadata helpers.
