# Calibration Capture Session Inspection

- created_at: 2026-06-28T23:09:38.871660Z
- session_id: 20260629_stereo_quality_hardware_probe
- topology: stereo
- accepted: False
- ready_for_target_detection: False
- image_count: 2
- read_image_count: 2
- recommendation: Recapture after fixing camera exposure, lighting, visibility, and calibration target placement.

## Issues

- frames/cam1_0001.png: low contrast / likely blank frame
- frames/cam2_0001.png: low contrast / likely blank frame

## Frame Metrics

| image | side | size | mean_luma | std_luma | max_luma | non_black_% | issues |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `frames/cam1_0001.png` | left | 1280x720 | 74.002 | 0.048 | 75.0 | 100.0 | low contrast / likely blank frame |
| `frames/cam2_0001.png` | right | 1280x720 | 74.025 | 0.156 | 76.0 | 100.0 | low contrast / likely blank frame |
