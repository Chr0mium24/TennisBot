# Test Replay Stereo Result 2026-07-20

## Scope

Added `scripts/test.py replay stereo` for offline dual-camera recording replay using
the existing TennisBot YOLO detector, runtime stereo calibration loader, stereo
matcher, and diagnostic renderer.

The replay path is diagnostic only. It processes recorded camera frames and does
not replace ROS/Gazebo closed-loop validation.

## Input

- Recording: `runs/recording/20260717_155414`
- Left/cam1 video: `runs/recording/20260717_155414/20260717_155414_video0.mkv`
- Right/cam2 video: `runs/recording/20260717_155414/20260717_155414_video2.mkv`
- Calibration package: `artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST`
- Frame window: `75..85`, inclusive
- Sync mode: `frame-index`

## Command

```bash
uv run scripts/test.py replay stereo \
  --recording runs/recording/20260717_155414 \
  --calibration-package artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST \
  --frame-start 75 \
  --frame-end 85 \
  --stride 1 \
  --sync frame-index \
  --record-root runs/yolo_eval \
  --record-session 20260720_replay_20260717_155414_frames75_85_latest_calib_fixed_overlay \
  --record-overlay \
  --predict-trajectory \
  --yolo-device cpu \
  --output-fps 6 \
  --progress-every 1
```

## Output

- Session: `runs/yolo_eval/20260720_replay_20260717_155414_frames75_85_latest_calib_fixed_overlay`
- Overlay video: `runs/yolo_eval/20260720_replay_20260717_155414_frames75_85_latest_calib_fixed_overlay/overlay.mp4`
- Overlay dimensions: `1880x404`
- Overlay frame count: `11`
- Overlay FPS: `6`

The overlay video is produced from the original dual MKV recording. The two
camera views are rendered at diagnostic display width and concatenated with the
right-side stereo panel.

## Summary Metrics

- Processed frame pairs: `11`
- Stereo matched pairs: `5`
- Left detection frames: `5`
- Right detection frames: `8`
- Both-camera detection frames: `5`
- Match rate: `0.4545`
- Median epipolar error: `3.408 px`
- Max epipolar error: `5.529 px`
- Median depth: `2.946 m`
- Depth range: `2.415..4.528 m`

## Overlay Layout Fix

The first replay overlay placed trajectory prediction text inside the right-side
diagnostic panel. Starting at frame 82, trajectory prediction became available
and overlapped the existing stereo metrics (`epi`, `reproj`, `conf/cost`).

The fixed overlay moves trajectory prediction text to a semi-transparent box on
the left camera view. The right-side diagnostic panel remains reserved for
stereo match metrics.

## Verification

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 uv run --extra test pytest -q
```

Result:

```text
11 passed in 0.20s
```

```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=nb_frames,duration,r_frame_rate,width,height \
  -of json \
  runs/yolo_eval/20260720_replay_20260717_155414_frames75_85_latest_calib_fixed_overlay/overlay.mp4
```

Result:

```json
{
  "streams": [
    {
      "width": 1880,
      "height": 404,
      "r_frame_rate": "6/1",
      "duration": "1.833333",
      "nb_frames": "11"
    }
  ]
}
```
