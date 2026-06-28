# Calibration Artifact Contracts

Date: 2026-06-28

These contracts define the files and minimum fields that `apps/live3d` and
runtime libraries may consume. They are tool output contracts, not implementation
APIs.

## Shared Rules

- Packages are directories under `artifacts/calibration/`.
- JSON files use UTF-8, two-space indentation, and stable key names.
- Numeric matrices are row-major nested arrays.
- Distances are meters unless a field explicitly says otherwise.
- Image coordinates and reprojection errors are pixels.
- Every package records `schema_version`, `created_at`, `source_session`, and
  `accepted`.
- Runtime code must treat `accepted: false` as not loadable unless it is running
  an explicit diagnostic workflow.

## Mono Package

Recommended paths:

```text
artifacts/calibration/cam1/
artifacts/calibration/cam2/
```

Required files:

```text
package.json
camera.json
calibration_opencv.yaml
verification.json
summary.md
```

### `package.json`

Required fields:

```json
{
  "schema_version": "calibration.mono.v1",
  "package_type": "mono_camera_calibration",
  "camera_id": "cam1",
  "created_at": "2026-06-28T00:00:00Z",
  "source_session": "captures/local/cam1_session",
  "target": {
    "type": "charuco",
    "profile": "dfoptix_charuco_15mm",
    "square_size_m": 0.015,
    "marker_size_m": 0.011
  },
  "image_size": {
    "width": 1920,
    "height": 1080
  },
  "files": {
    "camera": "camera.json",
    "opencv_yaml": "calibration_opencv.yaml",
    "verification": "verification.json",
    "summary": "summary.md"
  },
  "quality": {
    "accepted": true,
    "rms_reprojection_px": 0.35,
    "accepted_view_count": 25,
    "total_view_count": 30
  }
}
```

### `camera.json`

Required fields:

```json
{
  "schema_version": "calibration.camera_intrinsics.v1",
  "camera_id": "cam1",
  "image_size": {
    "width": 1920,
    "height": 1080
  },
  "camera_matrix": [
    [1200.0, 0.0, 960.0],
    [0.0, 1200.0, 540.0],
    [0.0, 0.0, 1.0]
  ],
  "distortion_model": "opencv_rational",
  "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
  "new_camera_matrix": [
    [1180.0, 0.0, 960.0],
    [0.0, 1180.0, 540.0],
    [0.0, 0.0, 1.0]
  ],
  "roi": {
    "x": 0,
    "y": 0,
    "width": 1920,
    "height": 1080
  }
}
```

### `verification.json`

Required fields:

```json
{
  "schema_version": "calibration.verification.v1",
  "accepted": true,
  "checks": [
    {
      "name": "rms_reprojection_px",
      "passed": true,
      "value": 0.35,
      "threshold": 0.5
    }
  ],
  "coverage": {
    "center": "good",
    "edges": "good",
    "corners": "acceptable"
  }
}
```

## Stereo Package

Recommended path:

```text
artifacts/calibration/stereo_cam1_cam2/
```

Required files:

```text
package.json
cam1.json
cam2.json
stereo.json
rectification.json
calibration_opencv.yaml
verification.json
summary.md
```

### `package.json`

Required fields:

```json
{
  "schema_version": "calibration.stereo.v1",
  "package_type": "stereo_camera_calibration",
  "camera_ids": ["cam1", "cam2"],
  "created_at": "2026-06-28T00:00:00Z",
  "source_session": "captures/local/stereo_cam1_cam2_session",
  "mono_sources": {
    "cam1": "artifacts/calibration/cam1",
    "cam2": "artifacts/calibration/cam2"
  },
  "target": {
    "type": "charuco",
    "profile": "dfoptix_charuco_15mm",
    "square_size_m": 0.015,
    "marker_size_m": 0.011
  },
  "files": {
    "cam1": "cam1.json",
    "cam2": "cam2.json",
    "stereo": "stereo.json",
    "rectification": "rectification.json",
    "opencv_yaml": "calibration_opencv.yaml",
    "verification": "verification.json",
    "summary": "summary.md"
  },
  "quality": {
    "accepted": true,
    "stereo_rms_reprojection_px": 0.42,
    "accepted_pair_count": 28,
    "total_pair_count": 32
  }
}
```

### `cam1.json` and `cam2.json`

Each file uses the mono `camera.json` contract. `camera_id` must match the
filename role.

### `stereo.json`

Required fields:

```json
{
  "schema_version": "calibration.stereo_extrinsics.v1",
  "left_camera_id": "cam1",
  "right_camera_id": "cam2",
  "rotation_left_to_right": [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
  ],
  "translation_left_to_right_m": [0.12, 0.0, 0.0],
  "essential_matrix": [
    [0.0, 0.0, 0.0],
    [0.0, 0.0, -0.12],
    [0.0, 0.12, 0.0]
  ],
  "fundamental_matrix": [
    [0.0, 0.0, 0.0],
    [0.0, 0.0, -0.0001],
    [0.0, 0.0001, 0.0]
  ],
  "baseline_m": 0.12
}
```

### `rectification.json`

Required fields:

```json
{
  "schema_version": "calibration.rectification.v1",
  "left_camera_id": "cam1",
  "right_camera_id": "cam2",
  "image_size": {
    "width": 1920,
    "height": 1080
  },
  "r1": [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
  ],
  "r2": [
    [1.0, 0.0, 0.0],
    [0.0, 1.0, 0.0],
    [0.0, 0.0, 1.0]
  ],
  "p1": [
    [1200.0, 0.0, 960.0, 0.0],
    [0.0, 1200.0, 540.0, 0.0],
    [0.0, 0.0, 1.0, 0.0]
  ],
  "p2": [
    [1200.0, 0.0, 960.0, -144.0],
    [0.0, 1200.0, 540.0, 0.0],
    [0.0, 0.0, 1.0, 0.0]
  ],
  "q": [
    [1.0, 0.0, 0.0, -960.0],
    [0.0, 1.0, 0.0, -540.0],
    [0.0, 0.0, 0.0, 1200.0],
    [0.0, 0.0, 8.3333333333, 0.0]
  ]
}
```

### `verification.json`

Required fields:

```json
{
  "schema_version": "calibration.stereo_verification.v1",
  "accepted": true,
  "checks": [
    {
      "name": "stereo_rms_reprojection_px",
      "passed": true,
      "value": 0.42,
      "threshold": 0.75
    },
    {
      "name": "baseline_m",
      "passed": true,
      "value": 0.12,
      "minimum": 0.05,
      "maximum": 0.5
    }
  ],
  "rectification": {
    "epipolar_error_px": 0.3,
    "accepted": true
  }
}
```

## Compatibility Notes

- `calibration_opencv.yaml` exists for OpenCV consumers and troubleshooting.
- Runtime code should prefer the JSON files for schema validation and typed
  loading.
- Tool internals may generate richer files, but the fields above are the minimum
  stable runtime surface.
