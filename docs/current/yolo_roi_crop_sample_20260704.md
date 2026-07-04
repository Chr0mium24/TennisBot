# YOLO Runtime ROI Proof Result - 2026-07-04

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

- Model: `tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`
- Sample list: `/home/cr/Codes/TennisBot/tools/yolo/workspace/runs/copy_paste_aug_1000_trial_20260703/val.txt`
- Sample limit: `60`
- Real images only: `True`
- Coarse full-frame imgsz: `416`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `cpu`
- CUDA available: `False`
- Torch: `2.12.1+cu130`

## Results

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| full | full_320 | 320 | 60 | 28 | 16 | 9 | 12 | 0.571 | 0.640 | 10.18 | 10.63 | 49.13 | full-frame baseline |
| full | full_416 | 416 | 60 | 28 | 17 | 15 | 11 | 0.607 | 0.531 | 14.92 | 20.95 | 33.52 | full-frame baseline |
| full | full_512 | 512 | 60 | 28 | 18 | 8 | 10 | 0.643 | 0.692 | 18.24 | 19.21 | 27.42 | full-frame baseline |
| oracle_roi | roi_768x432_320 (768x432) | 320 | 60 | 28 | 27 | 23 | 1 | 0.964 | 0.540 | 10.32 | 10.64 | 48.44 | label-placed ROI upper bound |
| oracle_roi | roi_960x540_320 (960x540) | 320 | 60 | 28 | 28 | 28 | 0 | 1.000 | 0.500 | 10.33 | 10.48 | 48.43 | label-placed ROI upper bound |
| coarse_roi | roi_768x432_320 (768x432) | 416+320 | 60 | 28 | 23 | 19 | 5 | 0.821 | 0.548 | 25.64 | 26.56 | 19.50 | same-frame full coarse plus ROI |
| coarse_roi | roi_960x540_320 (960x540) | 416+320 | 60 | 28 | 23 | 19 | 5 | 0.821 | 0.548 | 25.68 | 26.53 | 19.47 | same-frame full coarse plus ROI |

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
