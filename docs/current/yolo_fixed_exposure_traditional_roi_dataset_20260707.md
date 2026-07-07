# YOLO Fixed-Exposure Traditional ROI Dataset - 2026-07-07

## Goal

Package a fixed-exposure-only YOLO training dataset for server-side training.
This dataset intentionally excludes the older current/0260701 training data and
excludes all copy-paste samples.

This is a detector dataset packaging result only. It does not validate
ROS/Gazebo, stereo triangulation, trajectory prediction, or chassis control.

## Inputs

- Fixed-exposure zip:
  `tools/yolo/workspace/dataset/tennis_annotated_no_excluded.zip`
- Extracted fixed-exposure source:
  `tools/yolo/workspace/runs/fixed_exposure_source_20260707`
- Cloudy no-ball subset:
  `cloudy_background_cam1_frame_*.jpg`

## Data Policy

- Use fixed-exposure original images only.
- Do not include any current/old 0260701 dataset images.
- Do not generate or include copy-paste samples.
- Keep `cloudy_background_cam1` frames only as raw empty-label negatives.
- Generate extra samples only from fixed-exposure positive frames using:
  - ROI crop;
  - brightness/contrast/saturation/value changes;
  - optional horizontal flip;
  - optional small rotation;
  - optional Gaussian blur;
  - optional Gaussian noise.
- If an ROI would extend outside the source image, skip it. No padding,
  reflection fill, blur fill, or black fill is used for ROI boundaries.

## Generated Dataset

Output directory:

`tools/yolo/workspace/runs/fixed_exposure_traditional_roi_3000_20260707`

Zip package:

`tools/yolo/workspace/runs/fixed_exposure_traditional_roi_3000_20260707.zip`

SHA256:

`f4c3f0b937c5a387f960d1294a3fe0c7ea7bef9552a74347152528b9d9361663`

## Counts

| item | count |
|---|---:|
| fixed raw images | `1688` |
| fixed raw positive images | `1115` |
| fixed raw empty images | `573` |
| cloudy empty negatives | `483` |
| generated traditional ROI images | `3000` |
| total images | `4688` |
| total positive images | `4115` |
| total empty images | `573` |
| total boxes | `4115` |
| train images | `4212` |
| val images | `476` |

Kind counts:

| kind | count |
|---|---:|
| `raw_positive` | `1115` |
| `raw_negative` | `90` |
| `raw_cloudy_negative` | `483` |
| `traditional_roi_aug` | `3000` |

## ROI And Augmentation Settings

ROI sizes:

```text
960x540
1024x576
1280x720
1536x864
```

Ball anchor ratio grid:

```text
0.18, 0.32, 0.50, 0.68, 0.82
```

Traditional augmentation ranges:

| parameter | value |
|---|---:|
| brightness beta | `[-50, 50]` |
| contrast alpha | `[0.75, 1.30]` |
| saturation scale | `[0.75, 1.35]` |
| value scale | `[0.90, 1.10]` |
| horizontal flip probability | `0.15` |
| rotation probability | `0.40` |
| rotation degrees | `[-2.5, 2.5]` |
| Gaussian blur probability | `0.12` |
| Gaussian noise probability | `0.20` |

## Verification

The generated dataset was checked after creation:

- `train.txt` and `val.txt` image paths all exist.
- Each image has a corresponding label file.
- YOLO label values are normalized to `[0, 1]`.
- Label check result: `missing=0`, `bad_labels=0`.

## Upload Status

The zip was uploaded to:

`anilam@10.31.151.120:/home/anilam/Codes/TennisBot/tools/yolo/workspace/runs/fixed_exposure_traditional_roi_3000_20260707.zip`

The uploaded SHA256 matched the local package hash. Server-side training was
run from the extracted dataset and is recorded in:

`docs/current/yolo_fixed_exposure_traditional_roi_training_result_20260708.md`
