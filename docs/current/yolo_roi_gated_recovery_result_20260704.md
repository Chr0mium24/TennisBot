# YOLO ROI Gated Recovery Result - 2026-07-04

## Scope

This records the first algorithm fix after the continuous-sequence miss
diagnosis. It is still an offline monocular replay:

- no real ROS/chassis validation;
- no live camera capture;
- no stereo triangulation timing;
- no `/target/raw` catch-loop claim.

## Code Change

Updated `StatefulRoiTracker` and the `roi-track` benchmark:

- prefer detections near the predicted ROI center while locked;
- require confirmation before accepting a large locked-state jump;
- keep `SEARCH` acquisition as single-frame confirmation by default, because
  two-frame acquisition missed fast-moving balls in this sequence;
- add `--same-frame-search-on-miss-imgsz`, which immediately runs a full-frame
  recovery search in the same frame when a locked ROI result is not accepted.

The normal ROI remains `960x540@320`; the recovery search tested here uses
full-frame `512`.

## Sequence

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

Only the continuous labeled windows were used:

- cam1: first `124` frames, `49` GT boxes
- cam2: first `134` frames, `44` GT boxes

## Results

Raw reports:

- `docs/current/yolo_roi_recovery_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_roi_recovery_sequence_155008_cam2_labeled_window_20260704.md`
- `docs/current/yolo_roi_gated_search512_sequence_155008_cam1_labeled_window_20260704.md`
- `docs/current/yolo_roi_gated_search512_sequence_155008_cam2_labeled_window_20260704.md`

### Baseline Before Fix

These are the previous `search416/roi320` labeled-window measurements:

| stream | search | ROI | expanded | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 46 | 78 | 41 | 18 | 27 | 31 | 0.367 | 0.400 | 9.91 | 50.46 |
| cam2 | 103 | 31 | 11 | 17 | 9 | 27 | 0.386 | 0.654 | 22.28 | 22.44 |

### Gated Same-Frame Recovery

Settings:

- search imgsz: `416`
- ROI imgsz: `320`
- same-frame search-on-miss imgsz: `512`

| stream | search | ROI | expanded | same-frame search | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 49 | 75 | 25 | 44 | 29 | 34 | 20 | 0.592 | 0.460 | 16.59 | 29.88 | 30.13 |
| cam2 | 107 | 27 | 7 | 8 | 17 | 9 | 27 | 0.386 | 0.654 | 22.34 | 41.81 | 22.39 |

### Search512 Quality Mode

Settings:

- search imgsz: `512`
- ROI imgsz: `320`
- same-frame search-on-miss disabled

| stream | search | ROI | expanded | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 79 | 45 | 6 | 36 | 24 | 13 | 0.735 | 0.600 | 17.25 | 17.97 | 28.98 |
| cam2 | 107 | 27 | 5 | 22 | 5 | 22 | 0.500 | 0.815 | 17.37 | 17.96 | 28.78 |

## Readout

The fix helps cam1 substantially:

- recall improves from `0.367` to `0.592` with same-frame recovery;
- estimated stereo FPS drops from `50.46` to `30.13`;
- the drop is expected because `44 / 124` frames ran an extra full-frame
  `512` search.

The fix does not help cam2 in the `search416` runtime mode:

- cam2 already spends most frames in `SEARCH`;
- ROI recovery only triggers `8` times;
- the missing detections are mostly full-frame acquisition misses, so recovery
  after ROI miss cannot fix them.

For cam2, the only measured improvement is making SEARCH itself stronger:

- `search512/roi320` improves recall from `0.386` to `0.500`;
- precision improves from `0.654` to `0.815`;
- estimated stereo FPS is `28.78`.

## Decision

Keep normal ROI at `960x540@320`; making the box larger was not the main fix.

Use two runtime profiles:

- **Fast profile:** `search416/roi320`, no same-frame recovery. This is fastest
  when lock is stable, but recall remains weak on this capture.
- **Recovery profile:** `search416/roi320 + same-frame search512 on miss`. This
  improves cam1 and stays near `30 FPS`, but does not fix cam2 acquisition.
- **Quality profile:** `search512/roi320`. This is the best current recall and
  precision tradeoff on this capture, but it is below the `40-50 FPS` target.

The next real fix is still acquisition quality: either a better/split search
model, or stereo-confirmed search candidates in the real detector path.
