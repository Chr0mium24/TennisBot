# Multi-Agent Refactor Wave 4 Artifact Loaders Result

Date: 2026-06-28

Branch: `refactor/artifact-loaders`

## Summary

Wave 4 adds pure, parsed-object artifact validation and conversion helpers for:

- YOLO model package metadata from `tools/yolo`;
- stereo calibration package metadata from `tools/calibration`.

The loader boundary is now explicit:

```text
parsed artifact JSON -> validation result -> runtime contracts
```

No filesystem, browser fetch, model inference, SHA calculation, or large
artifact access is performed by these helpers.

## Loader Responsibilities

`packages/contracts` now describes raw JSON shapes for the runtime-facing
artifact files:

- YOLO `package.json`, `labels.json`, `preprocessing.json`, and
  `postprocessing.json`;
- stereo calibration `package.json`, `cam1.json`, `cam2.json`, `stereo.json`,
  `rectification.json`, and optional `verification.json`;
- row-major artifact matrix shapes used by calibration JSON.

`packages/core` now provides pure validation and conversion helpers:

- validate YOLO package fields, selected model entry, class `0 = tennis_ball`,
  preprocessing input size, and postprocessing class/threshold fields;
- validate stereo package fields, camera IDs, intrinsics, extrinsics,
  rectification matrices, and accepted quality/verification gates;
- convert snake_case calibration JSON into `CameraIntrinsics`,
  `StereoCalibration`, and `RectifiedStereoProjectionMatrices`;
- convert YOLO metadata into runtime model metadata with pending file, SHA-256,
  and byte-size checks represented as pluggable follow-up checks.

Validation returns explicit success/failure objects with actionable error
messages for ordinary invalid package data.

## Out Of Scope

This wave intentionally does not add:

- Node `fs` readers or browser `fetch` readers;
- real model file existence checks;
- SHA-256 or byte-size verification execution;
- YOLO inference adapters;
- calibration solving or OpenCV YAML parsing;
- `apps/live3d` integration;
- fallback discovery from training directories, datasets, or loose model files.

The live runtime can later provide IO adapters that parse JSON and pass those
objects into these helpers.

## Tests

Focused Bun fixtures cover:

- valid YOLO package metadata conversion;
- rejected YOLO metadata missing class `0 = tennis_ball`;
- valid stereo calibration package conversion;
- rejected stereo calibration package where quality and verification are not
  accepted;
- row-major matrix flattening for 3x3 and 3x4 artifact matrices.
