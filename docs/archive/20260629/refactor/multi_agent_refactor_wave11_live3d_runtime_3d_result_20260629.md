# Multi-Agent Refactor Wave 11 Live3D Runtime 3D Result

Date: 2026-06-29

Branch: `refactor/live3d-runtime-3d`

## Summary

Wave 11 connects Live3D runtime YOLO detections to the existing core stereo and
prediction algorithms without changing YOLO packaging, calibration packaging,
submodules, or real ROS/chassis behavior.

The new app-local runtime scene module consumes:

- left and right `YoloInferenceRuntimeStatus`;
- loaded or blocked `StereoCalibrationArtifactLoadStatus`;
- previous runtime 3D state;
- frame id and timestamp metadata.

It then:

- remaps runtime detection camera ids to the loaded calibration camera ids;
- calls `selectBestStereoPair`;
- calls `triangulateStereoPair`;
- keeps a runtime 3D trail;
- calls `predictTrajectory` once enough runtime points exist;
- reports explicit statuses for blocked calibration, missing detections, missing
  stereo pairs, triangulation failures, one-point tracking, and prediction-ready
  tracking.
- Lead review reset runtime 3D state when YOLO/camera runtime is stopped, used
  the left/right frame ids in runtime pair ids, preserved prior trail while
  waiting for a missing detection, and clamped configured trail length to at
  least one point.

## Files Changed

- `apps/live3d/src/runtime-scene.ts`
- `apps/live3d/src/runtime-scene.test.ts`
- `apps/live3d/src/main.ts`
- `apps/live3d/README.md`
- `docs/multi_agent_refactor_wave11_live3d_runtime_3d_result_20260629.md`

## Validation

These checks passed:

```bash
cd apps/live3d && bun test
cd apps/live3d && bun run typecheck
```

Final required validation was run after documentation and build updates:

```bash
cd apps/live3d && bun test
cd apps/live3d && bun run typecheck
cd apps/live3d && bun run build
git diff --check
```

Lead review result after runtime-state fixes: 38 passing tests, 0 failures.

## Residual Risk

This wave validates the software path with synthetic detections and calibration.
It does not validate real browser camera capture quality, the exported ONNX model
on real frames, real stereo calibration quality, or real ROS/chassis closed-loop catch
behavior. Those remain physical validation tasks.
