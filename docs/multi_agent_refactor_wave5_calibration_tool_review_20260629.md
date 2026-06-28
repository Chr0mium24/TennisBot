# Multi-Agent Refactor Wave 5 Calibration Tool Review

Date: 2026-06-29

## Reviewed Work

- Worker branch: `refactor/calibration-tool-runtime`
- Worker commit: `3a628e2 Implement calibration tool runtime`
- Lead review fix: `b1c2953 Tighten calibration package verification`
- Main merge commit: `eb718df Merge calibration tool runtime`

## Scope Review

Accepted scope:

- `tools/calibration/**`
- `docs/**`

Lead also added a top-level `.gitignore` entry for generated `artifacts/`
outputs after merge so local dry-run and future real calibration packages are
not accidentally committed.

No edits were made to:

- `CameraCalibLab/**`
- `TennisBallDetectorLab/**`
- `BallTrajectoryLab/**`
- `TennisWebSim/**`
- `TennisBotCV/**`
- `apps/**`
- `packages/**`
- `.gitmodules`

The pre-existing dirty `TennisBallDetectorLab` submodule state remained
untouched and unstaged.

## Review Findings

The worker implementation correctly created an independent `uv` Python project
under `tools/calibration` and kept the first GUI commands dry-run only:

- `tennisbot-calibration gui mono`
- `tennisbot-calibration gui stereo`
- `tennisbot-calibration package verify`

Generated `summary.md` and `review.html` files explicitly state that the output
is dry-run/non-hardware evidence and does not prove real camera capture,
OpenCV solve quality, or runtime catch-loop readiness.

Lead review found and fixed one validation gap before merge:

- `package verify` checked stereo package and verification acceptance, but did
  not reject `verification.rectification.accepted: false`.

The final merged verifier also rejects boolean values inside numeric
rectification matrices.

## Verification

Commands run after merge:

```bash
cd tools/calibration
uv sync
uv run pytest -q
uv run tennisbot-calibration --help
uv run tennisbot-calibration gui mono --camera-id cam1 --output ../../artifacts/calibration/cam1 --dry-run
uv run tennisbot-calibration gui mono --camera-id cam2 --output ../../artifacts/calibration/cam2 --dry-run
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --output ../../artifacts/calibration/stereo_cam1_cam2 --dry-run
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2

cd ../../packages/core
bun test
bun run typecheck
```

Results:

- `tools/calibration`: 8 tests passed.
- CLI smoke generated mono `cam1`, mono `cam2`, and stereo `cam1+cam2` dry-run
  packages.
- `package verify` accepted the generated stereo package with `dry_run: true`,
  `hardware_validated: false`, and no missing files.
- `packages/core`: 21 tests passed; TypeScript passed.
- A direct runtime-loader smoke loaded the generated stereo package through
  `loadStereoCalibrationArtifact` and produced `cam1`, `cam2`, and
  `baselineMeters: 0.12`.
- `git diff --check HEAD~5..HEAD`: passed with no output.

Generated `artifacts/**` smoke outputs were removed before commit.

## Remaining Work

This wave does not open physical USB cameras or run OpenCV calibration solving.
The next calibration wave should replace the dry-run frame source with real
local USB capture while preserving the same artifact contract and verifier.
