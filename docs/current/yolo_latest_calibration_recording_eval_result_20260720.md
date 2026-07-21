# YOLO Latest Calibration Recording Evaluation Result 2026-07-20

## Scope

Run offline YOLO detection and stereo geometry checks on the recent dual-camera
recordings using the latest accepted stereo calibration package.

This is an offline recording evaluation only. It does not validate the
real ROS/chassis closed-loop catching chain.

## Inputs

- Calibration package:
  `artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST`
- YOLO model:
  `artifacts/models/tennis_ball_yolo/model.pt`
- Recordings:
  `runs/recording/20260717_*`
- Camera mapping used:
  - `video0.mkv` -> cam1 / left / `/dev/video0`
  - `video2.mkv` -> cam2 / right / `/dev/video2`

The source recordings are 3840x2160. Frames were resized to 1280x720 before
YOLO inference and stereo matching so the inference frame size matches the
source resolution of the latest calibration package.

## Method

For each sampled stereo frame pair:

1. Read the matching `video0` and `video2` frame by frame index.
2. Resize both frames to 1280x720.
3. Run YOLO with `conf=0.05`, `iou=0.5`, `imgsz=1280`.
4. Use `RuntimeStereoCalibration.from_package(...)` with
   `artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST`.
5. Use `StereoBallMatcher` with the runtime geometry gates:
   - max epipolar error: `6 px`
   - min disparity: `1 px`
   - max disparity: `1200 px`
   - max depth: `12 m`

The 4 shorter sessions were sampled with `stride=5`. The long session
`20260717_155619` was sampled with `stride=30`.

## Results

| Session | Stride | Sampled pairs | Left det frames | Right det frames | Both det frames | Stereo matches | Match rate | Median epipolar px | Median depth m |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `20260717_155244` | 5 | 55 | 13 | 17 | 8 | 2 | 3.6% | 1.15 | 3.73 |
| `20260717_155338` | 5 | 59 | 3 | 22 | 2 | 0 | 0.0% | n/a | n/a |
| `20260717_155414` | 5 | 51 | 8 | 9 | 7 | 6 | 11.8% | 0.65 | 3.23 |
| `20260717_155523` | 5 | 46 | 17 | 9 | 7 | 2 | 4.3% | 1.60 | 5.29 |
| `20260717_155619` | 30 | 161 | 93 | 83 | 74 | 1 | 0.6% | 1.02 | 7.81 |

## Output artifacts

- Best visual sample output:
  `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/stereo_yolo_triangulation_sample.mp4`
- Best session summary:
  `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/summary.json`
- Best session metrics:
  `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/metrics.jsonl`
- Example matched frames:
  - `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/match_example_01_frame_000080.jpg`
  - `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/match_example_02_frame_000085.jpg`
  - `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/match_example_03_frame_000165.jpg`
  - `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/match_example_04_frame_000180.jpg`
  - `runs/yolo_eval/20260720_latest_calib_20260717_155414_stride5/match_example_05_frame_000185.jpg`

## Observations

- The best sampled recording is `20260717_155414`: 6 stereo matches from 51
  sampled pairs. The matched examples visually place the box on the small ball,
  and the median epipolar error is low at `0.65 px`.
- `20260717_155619` has many single-camera detections, but only one stereo
  match. In that run, 168 candidate pairs were evaluated; 123 were rejected by
  epipolar error, 42 by disparity, and 2 by depth. This points to many
  detections not being a valid left/right same-ball pair under the current
  frame-index pairing and calibration geometry.
- The extracted packet timestamps for the first frames of `20260717_155619`
  start within about 1 ms of each other, so the first-order issue is not an
  obvious large start-time offset. A stricter PTS-based pairing pass would still
  be useful before drawing final conclusions about the long recording.

## Conclusion

The latest calibration package is usable for offline stereo geometry on at
least some of the recent recordings. YOLO detections and triangulated stereo
matches are visible in `20260717_155414`, with plausible geometry quality.

The effect is not yet robust across the whole recent recording batch. The next
practical check is a PTS-synchronized offline replay, followed by reviewing
false positives and missed detections in the long `20260717_155619` session.
