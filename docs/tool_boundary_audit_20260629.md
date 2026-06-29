# Tool Boundary Audit

Date: 2026-06-29

## Scope

This audit checks the requested boundary:

- `tools/yolo` and `tools/calibration` remain standalone tool packages.
- `apps/` and `packages/` consume exported artifacts and shared contracts only.
- The main runtime must not import tool-package internals or legacy lab source
  code.

## Commands

```bash
rg "tools/(yolo|calibration)|tennisbot_yolo|tennisbot_calibration|CameraCalibLab|TennisBallDetectorLab|YOLO|calibration" apps packages -n
rg "from tennisbot_|import tennisbot_|CameraCalibLab|TennisBallDetectorLab|tools/yolo|tools/calibration" -n apps packages tools docs README.md
```

## Result

`apps/` and `packages/` do not import `tools/yolo`, `tools/calibration`,
`tennisbot_yolo`, `tennisbot_calibration`, `CameraCalibLab`, or
`TennisBallDetectorLab` internals.

The matches under `apps/` and `packages/` are limited to:

- artifact schema strings such as `calibration.stereo.v1`;
- runtime artifact paths such as `/artifacts/calibration/stereo_cam1_cam2`;
- UI/status copy for YOLO and calibration artifact loading;
- tests for artifact loaders, projection, runtime scene, and snapshots.

Matches under `tools/` are internal to each tool package. Matches under `docs/`
and `README.md` are command references, migration notes, or historical records.

## Conclusion

The active runtime boundary is intact:

```text
tools/yolo          -> writes artifacts/models/...
tools/calibration   -> writes artifacts/calibration/...
packages/core       -> validates/uses artifact metadata and runtime math
apps/live3d         -> loads artifacts over HTTP and renders the runtime UI
```

No main runtime code depends on YOLO training code, calibration solver code, or
legacy lab source modules.
