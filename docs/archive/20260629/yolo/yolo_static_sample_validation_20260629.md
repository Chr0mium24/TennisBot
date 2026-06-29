# YOLO Static Sample Validation

Date: 2026-06-29

## Scope

This validates the current `artifacts/models/tennis_ball_yolo` package against
existing labeled images from `TennisBallDetectorLab` without changing the legacy
submodule.

The goal was to distinguish three possible causes of zero detections in Live3D:

- no ball in the current live camera frames;
- Live3D ONNX postprocessing mismatch;
- weak or mis-thresholded model package.

## Dataset Inventory

Commands:

```bash
find TennisBallDetectorLab/yolo/dataset/images -type f \( -iname '*.jpg' -o -iname '*.png' \) | wc -l
find TennisBallDetectorLab/yolo/dataset/labels -type f -name '*.txt' | wc -l
```

Result:

```text
images: 132
labels: 661
nonempty labels matched to images: 109
```

## Initial PT Reference Scan

Command:

```bash
cd TennisBallDetectorLab
uv run python - <<'PY'
from pathlib import Path
from ultralytics import YOLO
model = YOLO('detector_package/model.pt')
pairs = []
for label in Path('yolo/dataset/labels').rglob('*.txt'):
    if not label.read_text().strip():
        continue
    matches = list(Path('yolo/dataset/images').rglob(label.stem + '.jpg'))
    if matches:
        pairs.append((matches[0], label))
records = []
for image, label in pairs:
    result = model.predict(str(image), imgsz=1280, conf=0.001, verbose=False)[0]
    conf = max([float(box.conf[0]) for box in result.boxes], default=0.0)
    records.append((conf, str(image)))
records.sort(reverse=True)
print(sum(1 for conf, _ in records if conf >= 0.05))
print(sum(1 for conf, _ in records if conf >= 0.01))
print(sum(1 for conf, _ in records if conf >= 0.001))
print(records[:3])
PY
```

Result:

```text
>=0.05 confidence: 0 / 109
>=0.01 confidence: 1 / 109
>=0.001 confidence: 24 / 109
best sample: yolo/dataset/images/cam1/device_a_indoor/indoor_ball_sample02_cam1_frame_000080.jpg
best PT confidence: 0.03673101216554642
```

The initial `detector_package/model.pt` did not produce any detection above the
packaged runtime threshold `0.05` on the matched labeled sample set.

## Replacement Model Candidate

The training run already contained a better candidate:

```text
TennisBallDetectorLab/yolo/runs/training/finetune_indoor_cam1/weights/best.pt
```

Static scan result for that candidate:

```text
>=0.05 confidence: 109 / 109
>=0.01 confidence: 109 / 109
>=0.001 confidence: 109 / 109
max confidence: 0.9584278464317322
min confidence: 0.06655905395746231
```

The model was copied into ignored local artifacts and exported to ONNX without
modifying `TennisBallDetectorLab` source files:

```text
artifacts/model_candidates/finetune_indoor_cam1/best.pt
artifacts/model_candidates/finetune_indoor_cam1/best.onnx
```

The runtime package was rebuilt with:

```bash
cd tools/yolo
uv run tennisbot-yolo package create \
  --output-dir ../../artifacts/models/tennis_ball_yolo \
  --model-pt ../../artifacts/model_candidates/finetune_indoor_cam1/best.pt \
  --model-onnx ../../artifacts/model_candidates/finetune_indoor_cam1/best.onnx \
  --default-model onnx \
  --eval-report ../../artifacts/model_candidates/finetune_indoor_cam1/eval_report.md \
  --eval-metrics ../../artifacts/model_candidates/finetune_indoor_cam1/eval_metrics.json
uv run tennisbot-yolo package verify --path ../../artifacts/models/tennis_ball_yolo
```

## ONNX Output Format Fix

The exported ONNX model returns:

```text
output0 dims: [1, 300, 6]
row format observed: x_min, y_min, x_max, y_max, score, class_id
```

This is an NMS-style `xyxy_pixels` output. The artifact already declares:

```json
{
  "box_format": "xyxy_pixels",
  "source_box_format": "YOLO normalized xywh"
}
```

Live3D previously decoded all six-value rows as `xywh + objectness + class0`,
which was wrong for this exported ONNX package. Live3D now carries
`postprocessing.json.box_format` through `packages/core` and decodes
`xyxy_pixels` rows correctly.

## Initial ONNX Static Result After Decode Fix

Sample:

```text
TennisBallDetectorLab/yolo/dataset/images/cam1/device_a_indoor/indoor_ball_sample02_cam1_frame_000080.jpg
```

Result with a diagnostic threshold of `0.001`:

```json
{
  "status": "ok",
  "boxes": [
    {
      "confidence": 0.003671795129776001,
      "xPx": 858.4777221679688,
      "yPx": 491.1565246582031,
      "widthPx": 58.957763671875,
      "heightPx": 59.050506591796875
    }
  ]
}
```

Result with the packaged runtime threshold of `0.05`:

```json
{
  "status": "ok",
  "boxes": []
}
```

## Replacement ONNX Static Result

The rebuilt runtime package uses the replacement `best.onnx` as the default
ONNX model. On the same sample, with the packaged runtime threshold `0.05`, the
Live3D ONNX backend returned:

```json
{
  "status": "ok",
  "boxes": [
    {
      "confidence": 0.9075310230255127,
      "xPx": 847.2093200683594,
      "yPx": 482.6033020019531,
      "widthPx": 70.90191650390625,
      "heightPx": 74.40151977539062
    }
  ]
}
```

The packaged `eval_metrics.json` now records:

```text
image_count: 109
confidence_threshold: 0.05
detected_at_threshold: 109
detection_rate_at_threshold: 1.0
max_confidence: 0.9584278464317322
min_confidence: 0.06655905395746231
```

## Conclusion

The Live3D ONNX postprocessing mismatch is fixed, and the default local runtime
YOLO artifact has been replaced with a better ONNX-default package derived from
`finetune_indoor_cam1/weights/best.pt`. Static sample detection now passes at
`confidence_threshold: 0.05`.

## Next Gate

- Re-run Live3D with a tennis ball visible in both USB camera views.
- Confirm nonzero runtime detections from live frames.
- Confirm the runtime 3D scene replaces the fixture fallback and updates the
  prediction curve.
