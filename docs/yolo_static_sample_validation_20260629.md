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

## PT Reference Scan

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

The current PT model does not produce any detection above the packaged runtime
threshold `0.05` on the matched labeled sample set.

## ONNX Output Format

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

## ONNX Static Result After Fix

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

## Conclusion

The Live3D ONNX postprocessing mismatch is fixed. The remaining zero-detection
behavior is now explained by model confidence quality and the packaged threshold:
the current model package is structurally loadable, but it is not detection
quality ready at `confidence_threshold: 0.05`.

## Next Gate

- Retrain or select a better tennis-ball detector package, or explicitly create
  a low-threshold diagnostic package for smoke testing.
- Re-run Live3D with a ball in both camera views after the detector package can
  produce nonzero detections at an acceptable confidence threshold.
