# YOLO ROI Miss Diagnosis - 2026-07-04

## Question

Why does the continuous sequence replay miss so many balls? Is the main fix to
make the ROI box larger, or to change the algorithm?

## Scope

This is an offline monocular replay diagnosis on the continuous labeled window
from:

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

It does not validate ROS/Gazebo, live cameras, stereo triangulation, or the real
catch loop.

## Model

`tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`

## Sweep

Baseline:

- search imgsz: `416`
- ROI: `960x540`
- ROI imgsz: `320`
- expanded ROI: `1280x720`
- lost after misses: `3`

Variants tested:

- `roi1280`: normal ROI `1280x720`, expanded ROI `1536x864`
- `roi1536`: normal ROI `1536x864`, expanded ROI `1920x1080`
- `lost5`: keep baseline ROI but allow `5` misses before returning to search
- `search512`: keep baseline ROI but search at imgsz `512`
- `roi416`: keep baseline ROI but run ROI inference at imgsz `416`

## Results

| stream | variant | search | ROI | expanded | locks | lost | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 first 124 | baseline | 46 | 78 | 41 | 20 | 19 | 18 | 27 | 31 | 0.367 | 0.400 | 14.28 | 35.03 |
| cam1 first 124 | roi1280 | 47 | 77 | 44 | 21 | 20 | 16 | 26 | 33 | 0.327 | 0.381 | 9.51 | 52.57 |
| cam1 first 124 | roi1536 | 45 | 79 | 45 | 19 | 18 | 20 | 26 | 29 | 0.408 | 0.435 | 10.01 | 49.95 |
| cam1 first 124 | lost5 | 34 | 90 | 65 | 16 | 15 | 11 | 19 | 38 | 0.224 | 0.367 | 9.94 | 50.31 |
| cam1 first 124 | search512 | 79 | 45 | 6 | 3 | 2 | 36 | 24 | 13 | 0.735 | 0.600 | 17.38 | 28.77 |
| cam1 first 124 | roi416 | 48 | 76 | 43 | 21 | 20 | 14 | 28 | 35 | 0.286 | 0.333 | 13.22 | 37.82 |
| cam2 first 134 | baseline | 103 | 31 | 11 | 4 | 4 | 17 | 9 | 27 | 0.386 | 0.654 | 14.44 | 34.62 |
| cam2 first 134 | roi1280 | 103 | 31 | 11 | 4 | 4 | 17 | 8 | 27 | 0.386 | 0.680 | 22.39 | 22.33 |
| cam2 first 134 | roi1536 | 103 | 31 | 11 | 4 | 4 | 17 | 10 | 27 | 0.386 | 0.630 | 14.44 | 34.62 |
| cam2 first 134 | lost5 | 96 | 38 | 18 | 4 | 3 | 17 | 9 | 27 | 0.386 | 0.654 | 14.28 | 35.01 |
| cam2 first 134 | search512 | 107 | 27 | 5 | 1 | 1 | 22 | 5 | 22 | 0.500 | 0.815 | 17.42 | 28.70 |
| cam2 first 134 | roi416 | 103 | 31 | 11 | 4 | 4 | 17 | 8 | 27 | 0.386 | 0.680 | 13.43 | 37.23 |

## Diagnosis

Making the ROI larger is not the main fix.

- cam1 improves only slightly with `1536x864`: recall `0.367 -> 0.408`.
- cam2 does not improve with larger ROI: recall stays `0.386`.
- `roi416` does not help and can hurt, likely because the lock is already wrong
  or the missed frames never enter a correct ROI.
- `lost5` is worse on cam1 because it keeps wrong locks alive longer.

The stronger signal is search/acquisition:

- `search512` improves cam1 recall from `0.367` to `0.735`.
- `search512` improves cam2 recall from `0.386` to `0.500`.
- The cost is lower FPS: about `28.7 FPS` estimated stereo on both streams.

The current tracker updates from the highest-confidence detection only. It has
no motion gate, no candidate confirmation, and no stereo confirmation in this
offline replay. Once it locks onto a false detection or reacquires the wrong
candidate, expanding the ROI or allowing more misses can preserve the wrong
state instead of recovering the ball.

## Recommended Fix

Do not primarily solve this by making the normal ROI bigger.

Use a two-level algorithm:

1. Keep normal locked ROI at `960x540` and expanded ROI at `1280x720`.
2. Add a recovery/search tier:
   - while locked, run fast `roi320`;
   - after one miss or near-edge detection, run expanded ROI;
   - after repeated misses, run `search512` for reacquisition;
   - once reacquired, return to `roi320`.
3. Add tracker gates before accepting a detection:
   - reject jumps that imply impossible pixel velocity;
   - prefer detections near the predicted center;
   - require 2-frame confirmation before switching to a far-away candidate;
   - in the real stereo path, require left/right epipolar-pair confirmation
     before updating the lock.

This keeps the high-FPS ROI path for stable frames while using the slower
`search512` only when the tracker is actually lost.

## Answer

The misses are mostly not because the ROI box is too small. They come from weak
full-frame acquisition and fragile lock updates. Bigger boxes can be used as a
temporary recovery window, but the algorithm needs motion/confirmation gates and
a higher-quality reacquisition path.
