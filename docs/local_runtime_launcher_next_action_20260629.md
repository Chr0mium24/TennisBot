# Local Runtime Launcher Next Action

Date: 2026-06-29

## Change

`scripts/start-local-runtime.ts` now prints the current physical validation next
action during normal startup. The launcher calls
`scripts/physical-validation-status.ts` with `/tmp` Markdown and JSON outputs,
so it does not modify repository docs during ordinary startup.

`--status` remains limited to surface readiness for scripts that expect concise
machine-readable output.

## Observed Output

```text
Local TennisBot runtime surfaces:
- Live3D: http://127.0.0.1:5178/ (reused)
- Calibration GUI: http://127.0.0.1:5188/ (reused)

Physical validation next action: Print the target SVG at 100%, measure one square, then record the measurement in this artifact.

Use Calibration GUI for Target -> Print Check -> Cam1 Mono -> Cam2 Mono -> Stereo.
Use Live3D after calibration and put a visible tennis ball in both camera views.
```

## Verification

```text
bun scripts/start-local-runtime.ts: printed the physical next action and exited 0 with reused services.
bun scripts/start-local-runtime.ts --status: ready for Live3D and Calibration GUI.
operator-preflight: passed.
```
