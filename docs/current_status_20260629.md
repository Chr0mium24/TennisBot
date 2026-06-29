# TennisBot Current Status

Date: 2026-06-29

## Current Step

The project is at the local operator validation stage.

The architecture simplification and main runtime split are in place:

- `tools/yolo` is the standalone YOLO package tool.
- `tools/calibration` is the standalone calibration package and review GUI.
- `packages/core` owns artifact validation, stereo pairing, triangulation, and
  trajectory prediction.
- `apps/live3d` owns the real-machine browser runtime for two USB cameras, YOLO
  inference, 3D point display, and prediction visualization.
- Legacy board/runtime code is outside the active local-machine flow.

## Ready Now

The local launcher reports both operator surfaces ready:

```text
ready  Live3D           http://127.0.0.1:5178/
ready  Calibration GUI  http://127.0.0.1:5188/
```

The current preflight passes:

```text
passed Live3D surface - http://127.0.0.1:5178/ returned 200.
passed Calibration GUI surface - http://127.0.0.1:5188/ returned 200.
passed YOLO package - artifacts/models/tennis_ball_yolo verified.
passed Stereo calibration package - artifacts/calibration/stereo_cam1_cam2 verified as accepted stereo package.
passed USB camera devices - /dev/video0 and /dev/video2 are present.
```

The latest committed runtime work added:

- local operator launcher;
- local runtime preflight;
- local physical validation checklist;
- local physical validation status script;
- target print measurement recorder;
- calibration target generation;
- calibration GUI target, mono, stereo, and package verification presets;
- Live3D readiness gates and hardware reports.

## Remaining Physical Gates

The remaining work requires real scene input, not another architecture split:

1. Print the generated ChArUco target at 100% scale and confirm one printed
   square measures 15 mm.
2. Run real `cam1` mono, `cam2` mono, then stereo calibration from fresh USB
   camera captures.
3. Put a visible tennis ball in both camera views and run Live3D hardware
   verification until it reaches `prediction-ready`.

## Next Commands

Start or check the local surfaces:

```bash
bun scripts/start-local-runtime.ts
bun scripts/start-local-runtime.ts --status
```

Run a non-destructive preflight:

```bash
bun scripts/operator-preflight.ts --output docs/local_runtime_preflight_YYYYMMDD.md
```

After the target and real calibration are ready, run the final Live3D hardware
evidence pass:

```bash
cd apps/live3d
bun run verify:hardware -- --prepare-uvc-controls --timeout-ms 30000 --output ../../docs/live3d_hardware_loop_ball_YYYYMMDD.md
```

The system should not be treated as physically accepted until the hardware
report reaches `prediction-ready`.
