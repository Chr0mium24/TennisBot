# YOLO Runtime ROI Proof Result - 2026-07-04

## Scope

This is an offline detector-throughput proof for the existing model.
It does not use real ROS/chassis, camera capture, stereo triangulation, target prediction, or chassis control.
The `oracle_roi` rows use labels to place the crop and are only an upper bound for locked ROI runtime.
The `coarse_roi` rows prove the full-frame-to-ROI crop path runs, but they are not a real tracker validation.

## Proof Plan

1. Measure the current full-frame detector at several `imgsz` values.
2. Measure one-crop locked ROI inference with label-placed crops to estimate the best possible detector budget after ROI lock.
3. Measure same-frame full coarse detection plus ROI refinement to prove the crop chain runs and expose its real cost.
4. Decide whether training should wait for a stateful runtime proof.

## Settings

- Model: `/home/cr/Codes/TennisBot/artifacts/models/tennis_ball_yolo/model.pt`
- Sample list: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/val.txt`
- Sample limit: `60`
- Real images only: `True`
- Coarse full-frame imgsz: `320`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `cpu`
- CUDA available: `False`
- Torch: `2.12.1+cu130`

## Results

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| full | full_320 | 320 | 60 | 28 | 5 | 19 | 23 | 0.179 | 0.208 | 9.33 | 16.81 | 53.58 | full-frame baseline |
| full | full_416 | 416 | 60 | 28 | 6 | 29 | 22 | 0.214 | 0.171 | 13.53 | 14.26 | 36.95 | full-frame baseline |
| full | full_512 | 512 | 60 | 28 | 10 | 32 | 18 | 0.357 | 0.238 | 16.83 | 17.07 | 29.71 | full-frame baseline |
| full | full_640 | 640 | 60 | 28 | 14 | 75 | 14 | 0.500 | 0.157 | 34.06 | 34.49 | 14.68 | full-frame baseline |
| oracle_roi | roi_768x432_320 (768x432) | 320 | 60 | 28 | 22 | 27 | 6 | 0.786 | 0.449 | 16.52 | 16.73 | 30.27 | label-placed ROI upper bound |
| oracle_roi | roi_960x540_320 (960x540) | 320 | 60 | 28 | 21 | 33 | 7 | 0.750 | 0.389 | 16.50 | 16.73 | 30.30 | label-placed ROI upper bound |
| oracle_roi | roi_960x540_416 (960x540) | 416 | 60 | 28 | 23 | 40 | 5 | 0.821 | 0.365 | 22.38 | 23.27 | 22.34 | label-placed ROI upper bound |
| oracle_roi | roi_1280x720_416 (1280x720) | 416 | 60 | 28 | 21 | 78 | 7 | 0.750 | 0.212 | 22.39 | 22.71 | 22.33 | label-placed ROI upper bound |
| oracle_roi | roi_960x540_512 (960x540) | 512 | 60 | 28 | 21 | 39 | 7 | 0.750 | 0.350 | 24.93 | 25.64 | 20.06 | label-placed ROI upper bound |
| oracle_roi | roi_1280x720_512 (1280x720) | 512 | 60 | 28 | 21 | 54 | 7 | 0.750 | 0.280 | 24.97 | 25.21 | 20.02 | label-placed ROI upper bound |
| coarse_roi | roi_768x432_320 (768x432) | 320+320 | 60 | 28 | 16 | 23 | 12 | 0.571 | 0.410 | 33.23 | 34.61 | 15.05 | same-frame full coarse plus ROI |
| coarse_roi | roi_960x540_320 (960x540) | 320+320 | 60 | 28 | 15 | 25 | 13 | 0.536 | 0.375 | 33.24 | 33.70 | 15.04 | same-frame full coarse plus ROI |
| coarse_roi | roi_960x540_416 (960x540) | 320+416 | 60 | 28 | 16 | 25 | 12 | 0.571 | 0.390 | 39.80 | 40.48 | 12.56 | same-frame full coarse plus ROI |
| coarse_roi | roi_1280x720_416 (1280x720) | 320+416 | 60 | 28 | 17 | 50 | 11 | 0.607 | 0.254 | 39.81 | 40.28 | 12.56 | same-frame full coarse plus ROI |
| coarse_roi | roi_960x540_512 (960x540) | 320+512 | 60 | 28 | 19 | 37 | 9 | 0.679 | 0.339 | 42.35 | 42.87 | 11.81 | same-frame full coarse plus ROI |
| coarse_roi | roi_1280x720_512 (1280x720) | 320+512 | 60 | 28 | 20 | 41 | 8 | 0.714 | 0.328 | 42.38 | 42.93 | 11.80 | same-frame full coarse plus ROI |

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
- This is not a target-board or real ROS/chassis proof; do not start more training until that stateful runtime mode is implemented and measured.
