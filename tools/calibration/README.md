# Calibration Tool Boundary

Date: 2026-06-28

`tools/calibration` is the future home for TennisBot camera calibration tooling.
Wave 1 is documentation and artifact contracts only. The existing
`CameraCalibLab` project remains the working implementation and must not be
moved or edited in this branch.

## Boundary

This tool owns:

- mono calibration for `cam1` and `cam2`;
- stereo calibration for the accepted `cam1 + cam2` pair;
- calibration target generation and inspection;
- capture and review workflows for calibration sessions;
- quality reports and runtime calibration package export.

This tool does not own:

- YOLO training or inference;
- 2D detection of tennis balls;
- triangulation, tracking, or trajectory prediction policy;
- live runtime UI;
- simulation control logic.

Runtime apps must consume exported calibration artifacts instead of importing
calibration tool internals.

## Target Layout

```text
tools/calibration/
  README.md
  artifact_contracts.md
  configs/
  src/
  tests/
  frontend/
    review/
```

`configs/`, `src/`, `tests/`, and `frontend/review/` are planned migration
targets. They are intentionally not created as implementation surfaces in Wave 1.

## Current Command Mapping

Current commands are run from `CameraCalibLab` with `uv`. Target commands should
keep equivalent behavior after the later migration, but the exact package entry
point may change.

| Current `CameraCalibLab` command | Target `tools/calibration` responsibility |
| --- | --- |
| `uv sync` | Install the calibration tool Python environment. |
| `uv run pytest -q` | Run calibration tool tests. |
| `uv run camera-calib-lab plugins list` | List available target, detector, solver, method, metric, and simulator plugins. |
| `uv run camera-calib-lab target generate --target ... --output ...` | Generate printable or display calibration targets. |
| `uv run camera-calib-lab target inspect --target ... --path ...` | Inspect a target image against the declared target definition. |
| `uv run camera-calib-lab capture passive --config ... --output ...` | Capture passive mono calibration images. |
| `uv run camera-calib-lab capture passive-gui --config ... --output ...` | Capture passive mono images through the GUI workflow. |
| `uv run camera-calib-lab capture phase-gui --config ... --output ...` | Capture phase-screen calibration sessions. |
| `uv run camera-calib-lab capture audit --session ... --output ...` | Audit captured calibration sessions before solving. |
| `uv run camera-calib-lab capture detect --session ... --detector ... --output ...` | Produce observation artifacts from a captured session. |
| `uv run camera-calib-lab detect run --session ... --method ...` | Run method-owned target detection before calibration. |
| `uv run camera-calib-lab calibrate run --session ... --method ... --output ...` | Solve one mono or stereo calibration run and write artifacts. |
| `uv run camera-calib-lab compare mono --session ... --methods ... --output ...` | Compare candidate mono calibration methods for a session. |
| `uv run camera-calib-lab compare stereo --config ... --output ...` | Compare candidate stereo calibration methods for a stereo session. |
| `uv run camera-calib-lab experiment run --config ... --output ...` | Run calibration experiments used to validate methods and quality gates. |
| `uv run camera-calib-lab simulate session ...` | Generate synthetic calibration sessions for method validation. |
| `uv run camera-calib-lab simulate phase-pattern ...` | Generate or validate phase-pattern simulation artifacts. |
| `uv run camera-calib-lab simulate pose-coverage ...` | Simulate target pose coverage for calibration planning. |
| `uv run camera-calib-lab simulate predict ...` | Predict expected calibration quality from saved session artifacts. |
| `uv run camera-calib-lab package export --run ...` | Export a runtime calibration package under `artifacts/calibration/`. |
| `uv run camera-calib-lab inspect review --artifact ...` | Open or describe the calibration artifact review UI. |
| `uv run camera-calib-lab hardware probe --output ...` | Probe real camera/display hardware for final calibration evidence. |
| `uv run camera-calib-lab hardware status ...` | Summarize hardware validation status from saved evidence artifacts. |
| `uv run camera-calib-lab hardware finalize ...` | Produce final hardware validation evidence from saved artifacts. |
| `uv run camera-calib-lab hardware audit ...` | Re-run the final hardware evidence audit gate. |
| `uv run camera-calib-lab hardware complete ...` | Verify the final hardware completion bundle without reopening devices. |
| `cd frontend/review && bun test` | Run calibration artifact review UI tests. |
| `cd frontend/review && bun run build` | Build the calibration artifact review UI. |

## Runtime Artifact Outputs

The target artifact roots are:

```text
artifacts/calibration/cam1/
artifacts/calibration/cam2/
artifacts/calibration/stereo_cam1_cam2/
```

Mono and stereo package contracts are defined in
[`artifact_contracts.md`](artifact_contracts.md).

## Import Existing CameraCalibLab Output

Existing CameraCalibLab mono/stereo `calibration.json` files can be converted
into the runtime stereo package contract without coupling the main runtime to
CameraCalibLab internals:

```bash
cd tools/calibration
uv run tennisbot-calibration package import-camera-calib-lab \
  --cam1 ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/cam1_mono/calibration/calibration.json \
  --cam2 ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/cam2_mono/calibration/calibration.json \
  --stereo ../../CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622/stereo/calibration/calibration.json \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2 \
  --source-session CameraCalibLab/calibration_packages/dfoptix_three_calibration_photos_cam1_60_20260622
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
```

The imported package is marked `dry_run: false` and `hardware_validated: true`.
If stereo quality metrics exceed runtime warning thresholds, the package remains
loadable for smoke testing but its summary records that recalibration is needed
before relying on 3D prediction accuracy.

## Migration Checklist

- [ ] Freeze the current `CameraCalibLab` baseline and record its commit.
- [ ] Confirm `uv run pytest -q` passes inside `CameraCalibLab`.
- [ ] Confirm `cd frontend/review && bun test && bun run build` passes inside
      `CameraCalibLab`.
- [ ] Copy implementation files into `tools/calibration` without changing
      behavior.
- [ ] Preserve `uv` for the Python project and `bun` for the TypeScript review
      frontend.
- [ ] Keep generated captures, runs, and packages ignored by git.
- [ ] Export mono packages that satisfy the mono artifact contract.
- [ ] Export stereo packages that satisfy the stereo artifact contract.
- [ ] Update runtime documentation to load only `artifacts/calibration/*`
      packages, not calibration source modules.
- [ ] Run contract tests against migrated sample mono and stereo packages.
- [ ] Remove or archive `CameraCalibLab` only after the migrated tool is verified
      and the lead agent approves the later wave.
