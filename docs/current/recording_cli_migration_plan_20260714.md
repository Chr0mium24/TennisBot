# Recording CLI migration plan

## Goal

Migrate the local scripts from `~/Codes/record` into this repository as a uv-managed Python tool, move the hard-coded camera recording controls into a YAML config, and expose recording through a CLI that follows the existing calibration tool style.

## Scope

- Add a `tools/recording` package with a `tennisbot-recording` console script.
- Preserve the single-camera recorder, dual-camera ffmpeg recorder, and single-camera Tk preview recorder behavior.
- Store the current recording camera controls in `tools/recording/configs/tennis_camera_recording.yaml`.
- Load exposure, white balance, brightness, gain, and related V4L2 controls from config by default, with CLI overrides for field work.
- Add a root wrapper at `scripts/recording.py` so operators can run commands from the repository root.
- Keep generated recordings under ignored `runs/recording` by default.

## Verification Plan

1. Unit-test config loading and command generation without camera hardware.
2. Run CLI dry-runs for single and dual recording.
3. Run the package test suite through `uv`.
4. Document verification results before committing.
