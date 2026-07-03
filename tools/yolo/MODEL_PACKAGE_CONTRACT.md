# YOLO Model Package Contract

Date: 2026-07-03

This contract defines the model package consumed by the vision runtime. The
package is produced by `tools/yolo` and stored under
`artifacts/models/`.

## Package Directory

Default package path:

```text
artifacts/models/tennis_ball_yolo/
  package.json
  labels.json
  preprocessing.json
  postprocessing.json
  model.pt
  model.onnx
  model.rknn
  eval_report.md
  eval_metrics.json
  package_manifest.json
```

Only one model file is required at runtime, but a package may include multiple
formats. The vision runtime chooses the first supported format
according to its detector configuration.

## Required Files

### `package.json`

```json
{
  "name": "tennis_ball_yolo",
  "version": "0.1.0",
  "contract": "tennisbot.yolo-model-package",
  "contract_version": "0.1.0",
  "created_at": "2026-06-28T00:00:00Z",
  "producer": {
    "tool": "tools/yolo",
    "source": "TennisBallDetectorLab migration"
  },
  "models": {
    "pt": {
      "path": "model.pt",
      "sha256": "<hex>",
      "bytes": 0,
      "runtime": "ultralytics"
    },
    "onnx": {
      "path": "model.onnx",
      "sha256": "<hex>",
      "bytes": 0,
      "runtime": "onnxruntime"
    },
    "rknn": {
      "path": "model.rknn",
      "sha256": "<hex>",
      "bytes": 0,
      "runtime": "rknn"
    }
  },
  "default_model": "pt",
  "labels": "labels.json",
  "preprocessing": "preprocessing.json",
  "postprocessing": "postprocessing.json",
  "evaluation": {
    "report": "eval_report.md",
    "metrics": "eval_metrics.json"
  }
}
```

Rules:

- `contract` must equal `tennisbot.yolo-model-package`.
- `contract_version` uses semver and must change when runtime fields change.
- `models` must include at least one supported entry.
- Every listed model file must include `path`, `sha256`, `bytes`, and
  `runtime`.
- `default_model` must reference a key in `models`.

The current `TennisBallDetectorLab` exporter writes `metadata.json`. During
migration, `tools/yolo package` should either write both `package.json` and
`metadata.json` for compatibility or replace consumers in the same release.

### `labels.json`

```json
{
  "classes": [
    {
      "id": 0,
      "name": "tennis_ball"
    }
  ],
  "format": "YOLO detect normalized xywh"
}
```

Rules:

- Class id `0` is `tennis_ball`.
- The runtime may reject packages with missing or renamed class `0` until
  multi-class support is explicitly added.

### `preprocessing.json`

```json
{
  "input_color": "RGB",
  "input_size": {
    "width": 1280,
    "height": 1280
  },
  "resize": {
    "mode": "letterbox",
    "preserve_aspect_ratio": true,
    "stride": 32
  },
  "normalization": {
    "scale": 0.00392156862745098,
    "mean": [0.0, 0.0, 0.0],
    "std": [1.0, 1.0, 1.0]
  }
}
```

Rules:

- `input_color` must be explicit. Runtime adapters may convert camera BGR/RGB
  frames before inference.
- `input_size` is the inference tensor size, not necessarily the camera frame
  size.
- `resize.mode` should be `letterbox` for Ultralytics-compatible packages.

### `postprocessing.json`

```json
{
  "task": "single-class tennis ball detection",
  "box_format": "xyxy_pixels",
  "source_box_format": "YOLO normalized xywh",
  "class_id": 0,
  "confidence_threshold": 0.05,
  "nms_iou_threshold": 0.5,
  "max_detections": 10,
  "runtime_output": "detections"
}
```

Rules:

- `confidence_threshold` is the default startup threshold for the vision
  runtime.
- Runtime launch parameters may override the threshold, but package defaults
  remain the source of truth for reproducible runs.
- The runtime output must be convertible to the shared detection contract:

```json
{
  "camera_id": "cam1",
  "timestamp_ns": 0,
  "bbox_xyxy": [0.0, 0.0, 0.0, 0.0],
  "confidence": 0.0,
  "class_id": 0,
  "label": "tennis_ball",
  "frame_size": {
    "width": 1920,
    "height": 1080
  }
}
```

### `eval_metrics.json`

Minimum fields:

```json
{
  "dataset": {
    "labels": 0,
    "positives": 0,
    "negatives": 0,
    "cameras": {
      "cam1": 0,
      "cam2": 0
    }
  },
  "model": {
    "precision": null,
    "recall": null,
    "map50": null,
    "map50_95": null
  }
}
```

If full model metrics are unavailable, fields may be `null`, but the package
must include `eval_report.md` explaining the gap.

`tools/yolo package create` can copy a supplied `eval_report.md` and
`eval_metrics.json` into the package. Runtime packages intended for hardware
testing should include at least a static smoke report or a full validation
report.

## Runtime Validation

Before the vision runtime starts inference, it should validate:

- package directory exists;
- `package.json`, `labels.json`, `preprocessing.json`, and
  `postprocessing.json` parse successfully;
- class `0` maps to `tennis_ball`;
- selected model file exists and its SHA-256 matches when present;
- preprocessing input size and postprocessing thresholds are present;
- selected runtime adapter supports the chosen model format.

Validation failures should mention the missing package field or file and should
not fall back to training directories.

## Compatibility Notes

The current `TennisBallDetectorLab` handoff package contains:

- `metadata.json`;
- `labels.json`;
- `preprocessing.json`;
- `postprocessing.json`;
- optional `model.pt`, `model.onnx`, `model.rknn`;
- `eval_report.md`;
- `eval_metrics.json`;
- `package_manifest.json`.

The target contract keeps those data files but renames the runtime entrypoint
to `package.json` and makes the vision runtime the consumer.
