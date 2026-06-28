# Multi-Agent Refactor Wave 5 Calibration Tool Result

Date: 2026-06-29

## Plan

- Add a standalone `uv` Python project under `tools/calibration`.
- Expose `tennisbot-calibration` with dry-run `gui mono`, dry-run `gui stereo`,
  and `package verify` commands.
- Generate deterministic local review artifacts only; do not open physical
  cameras or claim real calibration validation.
- Verify mono and stereo packages against the documented Wave 5 artifact files
  and accepted flags.
- Keep generated `artifacts/**` outputs out of the commit.

## Result

- Implemented deterministic mono and stereo dry-run package writers.
- Added local `summary.md` and `review.html` outputs that explicitly label the
  evidence as dry-run/non-hardware.
- Added package verification for required files, accepted gates, camera ID
  consistency, and stereo rectification matrix shapes.
- Added focused tests for CLI help, generated packages, verification rejection,
  and row-major rectification matrices.

Lead review tightened the final merged version to also reject stereo packages
whose `verification.json` omits `rectification.accepted: true`. It also rejects
boolean values inside numeric rectification matrices.

## Verification

Completed local run:

```bash
cd tools/calibration
uv sync                                            # passed
uv run pytest -q                                  # 8 passed after lead review
uv run tennisbot-calibration --help               # lists gui mono, gui stereo, package verify
uv run tennisbot-calibration gui mono --camera-id cam1 --output ../../artifacts/calibration/cam1 --dry-run
uv run tennisbot-calibration gui mono --camera-id cam2 --output ../../artifacts/calibration/cam2 --dry-run
uv run tennisbot-calibration gui stereo --left-camera-id cam1 --right-camera-id cam2 --output ../../artifacts/calibration/stereo_cam1_cam2 --dry-run
uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2
cd ../..
git diff --check                                  # passed
```

The generated stereo package verification returned:

```json
{
  "accepted": true,
  "dry_run": true,
  "hardware_validated": false,
  "missing_files": [],
  "package_kind": "stereo"
}
```

Generated `artifacts/**` smoke outputs were removed before commit.

After merge, the generated stereo dry-run package was also loaded through
`packages/core`'s `loadStereoCalibrationArtifact` helper. That smoke check
returned `cam1`, `cam2`, and `baselineMeters: 0.12`, confirming the generated
contract shape is consumable by the runtime loader.
