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
- `package verify`

## GUI Behavior

The Capture and Solve panels now show a `Run` button beside each generated
command. Results are rendered inline with status, exit code/duration detail,
stdout, and stderr. Rejected commands return a structured `rejected` result
instead of being executed.

When a command writes a JSON artifact, the server returns it with the command
result. The browser automatically imports returned JSON artifacts into the
review workspace, so a capture/inspect/detect/solve sequence can update the gate
state without manual file picker steps.

The review server now binds to `127.0.0.1` by default because it can execute
local commands. Set `HOST=0.0.0.0` only for deliberate LAN exposure.

## Verification

Commands:

```bash
cd tools/calibration/frontend/review
bun test
bun run build
cd ../..
uv run pytest -q
```

Results:

```text
bun test: 12 passed, 0 failed.
bun run build: passed.
uv run pytest -q: 19 passed.
```

The added tests cover command planning without shell execution, rejection of
non-whitelisted commands, rejection of unsafe paths/devices, and API rejection
responses, plus generated JSON artifact collection from command output paths and
`package verify` stdout.

Local API smoke:

```bash
curl -X POST http://127.0.0.1:5188/api/calibration/run \
  -H 'content-type: application/json' \
  --data '{"command":"uv run tennisbot-calibration package verify --path ../../artifacts/calibration/stereo_cam1_cam2"}'
```

Result:

```text
status: passed
exitCode: 0
package_kind: stereo
accepted: true
dry_run: false
hardware_validated: true
returned_artifacts: 1
```

## Remaining Field Work

- Use the GUI command bridge with a visible ChArUco target to run capture,
  inspect, detect, mono solve, and stereo solve from the local browser.
- Add explicit accept/reject annotations for individual preview frames if manual
  frame curation is needed before solve.
