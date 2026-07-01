# Local Physical Validation Status

- created_at: 2026-06-29T04:21:35.375Z
- result: incomplete
- next_action: Print the target SVG at 100%, measure one square, then record the measurement in this artifact.

## Gates

- passed: ChArUco target metadata - dfoptix ChArUco target metadata is accepted at 15.0 mm square size.
- blocked: Printed target measurement - no recorded 15.0 mm print measurement was found.
- blocked: cam1 mono calibration - cam1 mono package is accepted but not hardware validated.
- blocked: cam2 mono calibration - cam2 mono package is accepted but not hardware validated.
- blocked: Stereo calibration - stereo package is hardware validated, but mono prerequisites are incomplete.
- blocked: Live3D prediction-ready hardware run - no Live3D hardware report has reached prediction-ready.

## Next Action

Print the target SVG at 100%, measure one square, then record the measurement in this artifact.

## Details

### ChArUco target metadata

- status: passed
- detail: dfoptix ChArUco target metadata is accepted at 15.0 mm square size.

```text
{
  "path": "artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
  "accepted": true,
  "profile": "dfoptix_charuco_15mm",
  "square_size_mm": 15,
  "files": {
    "metadata": "../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.json",
    "png": "../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.png",
    "svg": "../../artifacts/calibration_targets/dfoptix_charuco_15mm_300dpi.svg"
  }
}
```

### Printed target measurement

- status: blocked
- detail: no recorded 15.0 mm print measurement was found.
- next: Print the target SVG at 100%, measure one square, then record the measurement in this artifact.

```text
artifacts/calibration_targets/dfoptix_charuco_15mm_print_check.json
```

### cam1 mono calibration

- status: blocked
- detail: cam1 mono package is accepted but not hardware validated.
- next: Capture real cam1 ChArUco frames, solve mono, and verify the package.

```text
{
  "path": "artifacts/calibration/cam1/package.json",
  "accepted": true,
  "dry_run": true,
  "hardware_validated": false,
  "accepted_view_count": 25,
  "rms_reprojection_px": 0.35
}
```

### cam2 mono calibration

- status: blocked
- detail: cam2 mono package is accepted but not hardware validated.
- next: Capture real cam2 ChArUco frames, solve mono, and verify the package.

```text
{
  "path": "artifacts/calibration/cam2/package.json",
  "accepted": true,
  "dry_run": true,
  "hardware_validated": false,
  "accepted_view_count": 25,
  "rms_reprojection_px": 0.35
}
```

### Stereo calibration

- status: blocked
- detail: stereo package is hardware validated, but mono prerequisites are incomplete.
- next: Complete real cam1 and cam2 mono calibration before accepting the stereo gate.

```text
{
  "path": "artifacts/calibration/stereo_cam1_cam2/package.json",
  "mono_prerequisites": [
    {
      "id": "cam1-mono",
      "status": "blocked",
      "detail": "cam1 mono package is accepted but not hardware validated."
    },
    {
      "id": "cam2-mono",
      "status": "blocked",
      "detail": "cam2 mono package is accepted but not hardware validated."
    }
  ],
  "accepted": true,
  "dry_run": false,
  "hardware_validated": true,
  "accepted_pair_count": 33,
  "stereo_rms_reprojection_px": 0.42365210023675176,
  "baseline_m": 0.05248616443700974
}
```

### Live3D prediction-ready runtime run

- status: blocked
- detail: no Live3D run has reached prediction-ready.
- next: Put a visible tennis ball in both camera views and watch the browser
  readiness gates until prediction is ready.

```text
- Result: failed
- Error: Runtime 3D prediction did not reach ready.
- Max left detections: 0
- Max right detections: 0
- Max prediction samples: 0
- Runtime 3D codes: idle, left-detections-missing
```
