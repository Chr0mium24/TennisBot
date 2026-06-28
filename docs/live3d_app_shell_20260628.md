# Live3D App Shell Result

Date: 2026-06-28

Branch: `refactor/live3d-shell`

## Scope

Created the first `apps/live3d` frontend shell for the real-machine stereo UI.
The shell is intentionally limited to frontend layout and fixture data.

## UX Defined

- Left and right USB camera panels.
- Static 2D YOLO-style detection overlays.
- 3D scene area with a placeholder ball point, trail, predicted curve, and
  landing marker.
- Runtime status panel for camera, model, calibration, tracking, and prediction.
- Visible fixture-mode warning that states no real cameras, YOLO inference,
  stereo tracking, triangulation, or prediction validation has occurred.

## Config Placeholders

- Left camera device: `/dev/video0`.
- Right camera device: `/dev/video2`.
- YOLO model package path: `../../artifacts/models/tennis_ball_yolo`.
- Stereo calibration package path:
  `../../artifacts/calibration/stereo_cam1_cam2`.

## Fixture Mode Boundary

Fixture mode is static UI data only. It must not be used as evidence that the
real TennisBot receiving loop works. Real validation still requires USB camera
streams, an exported YOLO model package, an accepted stereo calibration package,
core triangulation, tracking, and prediction.
