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

- Model: `runs/detect/tools/yolo/workspace/runs/training/small_yolo26_micro_p2_no_p5_aug1000_imgsz640_20260706/weights/best.pt`
- Sample list: `/tmp/tennisbot_155008_samples.txt`
- Sample limit: `0`
- Real images only: `False`
- Coarse full-frame imgsz: `640`
- Confidence threshold: `0.05`
- Prediction IoU setting: `0.7`
- Match IoU: `0.5`
- Device argument: `0`
- CUDA available: `True`
- Torch: `2.12.1+cu130`

## Results

| mode | profile | imgsz | images | gt | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS | notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| full | full_640 | 640 | 866 | 93 | 20 | 65 | 73 | 0.215 | 0.235 | 5.05 | 5.71 | 99.07 | full-frame baseline |
| oracle_roi | roi_960x540_320 (960x540) | 320 | 866 | 93 | 32 | 68 | 61 | 0.344 | 0.320 | 3.86 | 3.98 | 129.49 | label-placed ROI upper bound |
| coarse_roi | roi_960x540_320 (960x540) | 640+320 | 866 | 93 | 25 | 111 | 68 | 0.269 | 0.184 | 9.21 | 9.63 | 54.28 | same-frame full coarse plus ROI |

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
