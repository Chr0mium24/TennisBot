# Calibration Review GUI Command Bridge

Date: 2026-06-29

## Scope

`tools/calibration/frontend/review` now includes a local command bridge for the
calibration review GUI. The browser still builds commands from reviewed fields,
but the Bun server can execute a restricted subset of `uv run
tennisbot-calibration ...` commands through `/api/calibration/run`.

The bridge does not invoke a shell. It tokenizes the reviewed command, validates
the command prefix and subcommand, validates allowed flags, restricts device
paths to `/dev/videoN`, and restricts write outputs to repository `artifacts/`
or `docs/`.

Allowed command families:

- `capture mono`
- `capture stereo`
- `capture inspect`
- `capture detect-charuco`
- `calibrate mono`
- `calibrate stereo`
- `target charuco`
- `package verify`

## GUI Behavior

The Target, Capture, and Solve panels now show a `Run` button beside each
generated command. Results are rendered inline with status, exit code/duration
detail, stdout, and stderr. Rejected commands return a structured `rejected`
result instead of being executed.

When a command writes a JSON artifact, the server returns it with the command
result. The browser automatically imports returned JSON artifacts into the
review workspace, so a capture/inspect/detect/solve sequence can update the gate
state without manual file picker steps. The workspace now treats
`calibration.target_sheet.v1` as a first-class Target gate, so the visible GUI
flow starts with target-sheet generation before capture, inspect, detect, solve,
and package verification. The toolbar presets `Cam1 Mono`, `Cam2 Mono`, and
`Stereo` update capture, observations, solve, report, and verify paths together.

The review server now binds to `127.0.0.1` by default because it can execute
local commands. Set `HOST=0.0.0.0` only for deliberate LAN exposure.

## Verification

Commands:

```bash
cd tools/calibration/frontend/review
bun test
bun run build
curl -sS http://127.0.0.1:5188/assets/main.js | rg 'Cam1 Mono|Cam2 Mono|package verify|target charuco|calibration.target_sheet.v1'
cd ../..
uv run pytest -q
```

Results:

```text
bun test: 12 passed, 0 failed.
bun run build: passed.
bundle smoke: mono/stereo presets, package verify, target charuco command, and
target-sheet schema present.
uv run pytest -q: 20 passed.
```

The added tests cover command planning without shell execution, rejection of
non-whitelisted commands, rejection of unsafe paths/devices, and API rejection
responses, plus generated JSON artifact collection from command output paths and
`package verify` stdout. Frontend workspace tests cover Target artifact
classification, the Target workflow gate, target command generation, and
target-sheet metadata returned by `target charuco`. They also cover
`packageVerification` artifact classification and package verify command
generation.

Local API smoke:

```bash
curl -X POST http://127.0.0.1:5188/api/calibration/run \
  -H 'content-type: application/json' \
  --data '{"command":"uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2"}'
curl -X POST http://127.0.0.1:5188/api/calibration/run \
  -H 'content-type: application/json' \
  --data '{"command":"uv run tennisbot-calibration target charuco --output ../../artifacts/calibration_targets/bridge_target.png"}'
```

Result:

```text
package verify: status=passed, exitCode=0, package_kind=stereo,
accepted=true, dry_run=false, hardware_validated=true, returned_artifacts=1.
target charuco: status=passed, exitCode=0,
returned_artifact_schema=calibration.target_sheet.v1, accepted=true.
```

## Remaining Field Work

- Use the GUI command bridge with a visible ChArUco target to run capture,
  inspect, detect, mono solve, and stereo solve from the local browser.
- Add explicit accept/reject annotations for individual preview frames if manual
  frame curation is needed before solve.
