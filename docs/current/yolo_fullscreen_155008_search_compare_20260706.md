# YOLO Runtime ROI Proof Result - 2026-07-06

## Scope

This is an offline detector-throughput proof for the existing model.
It does not use ROS/Gazebo, camera capture, stereo triangulation, target prediction, or chassis control.
The `oracle_roi` rows use labels to place the crop and are only an upper bound for locked ROI runtime.
The `coarse_roi` rows prove the full-frame-to-ROI crop path runs, but they are not a real tracker validation.

## Proof Plan

1. Measure the current full-frame detector at several `imgsz` values.
2. Measure one-crop locked ROI inference with label-placed crops to estimate the best possible detector budget after ROI lock.
3. Measure same-frame full coarse detection plus ROI refinement to prove the crop chain runs and expose its real cost.
4. Decide whether training should wait for a stateful runtime proof.

## Settings

- Model: `/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo/model.pt`
- Sample list: `/tmp/tennisbot_155008_samples.txt`
- Sample limit: `0`
- Real images only: `False`
- Coarse full-frame imgsz: `416`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `0`
- CUDA available: `True`
- Torch: `2.12.1+cu130`

## Results

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| full | full_320 | 320 | 866 | 93 | 21 | 694 | 72 | 0.226 | 0.029 | 4.17 | 4.71 | 119.79 | full-frame baseline |
| full | full_416 | 416 | 866 | 93 | 27 | 424 | 66 | 0.290 | 0.060 | 4.39 | 4.74 | 113.94 | full-frame baseline |
| full | full_512 | 512 | 866 | 93 | 31 | 321 | 62 | 0.333 | 0.088 | 4.65 | 5.09 | 107.56 | full-frame baseline |
| full | full_640 | 640 | 866 | 93 | 37 | 509 | 56 | 0.398 | 0.068 | 5.17 | 5.86 | 96.78 | full-frame baseline |
| oracle_roi | roi_960x540_320 (960x540) | 320 | 866 | 93 | 58 | 435 | 35 | 0.624 | 0.118 | 4.02 | 4.27 | 124.41 | label-placed ROI upper bound |
| coarse_roi | roi_960x540_320 (960x540) | 416+320 | 866 | 93 | 43 | 380 | 50 | 0.462 | 0.102 | 9.05 | 9.59 | 55.24 | same-frame full coarse plus ROI |

## Readout

- `full` is the current full-frame detector path on one camera frame.
- `oracle_roi` measures one crop per camera frame after the ROI is already known.
- `coarse_roi` runs a full-frame coarse pass, crops around the best coarse detection, then runs ROI refinement.
- `est stereo FPS` assumes left and right camera images are processed sequentially with the same per-image median.
- Passing `30 FPS` in `oracle_roi` only proves detector budget feasibility while locked; it does not prove tracking or real catch-loop behavior.

## Small Object Compression Note

- Training cannot recover image detail that was destroyed by full-frame downscaling.
- A `10px` to `16px` tennis ball in a `3840px`-wide frame becomes roughly `0.8px` to `1.7px` at `imgsz=320/416`.
- The same object inside a `960px`-wide ROI becomes roughly `3.3px` to `6.9px` at `imgsz=320/416`.
- This is why ROI/crop must happen before the YOLO resize step; otherwise the far-ball signal is already gone.

## Decision

- Low-`imgsz` full-frame rows can meet the FPS target, but their recall is too low for the tennis-ball task.
- Low-`imgsz` locked ROI rows can meet the FPS target in this detector-only proof and have much better recall than full-frame at the same `imgsz`.
- Same-frame `coarse_roi` does not meet the FPS target because it runs two detections per camera frame.
- The next runtime step is a stateful ROI mode: full-frame search only while unlocked or periodically, then ROI-only inference while locked.
- This is not a target-board or ROS/Gazebo proof; do not start more training until that stateful runtime mode is implemented and measured.
