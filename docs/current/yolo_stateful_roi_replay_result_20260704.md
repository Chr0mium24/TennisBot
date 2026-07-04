# YOLO Stateful ROI Replay Result - 2026-07-04

## Scope

This replay exercises a stateful visual ROI tracker on ordered real camera
frames. It decides whether a frame runs full-frame `SEARCH` or ROI-only
`LOCKED` inference.

This is still an offline monocular detector replay:

- no ROS/Gazebo;
- no stereo triangulation;
- no target prediction;
- no chassis/control logic;
- no claim of a real catch-loop validation.

## Logic Added

Added reusable stateful ROI tracking logic:

- `tools/yolo/src/tennisbot_yolo/roi_tracking.py`
- CLI replay entry: `tennisbot-yolo benchmark roi-track`

State behavior:

- `SEARCH`: run full-frame detection.
- `LOCKED`: predict next ROI center from previous center and pixel velocity.
- Use normal ROI while stable.
- Expand ROI after a miss or when the detection is near the ROI edge.
- Return to `SEARCH` after configured consecutive misses.

The tracker only decides where to crop the next frame. It is not target landing
prediction and does not replace ROS/Gazebo backend pose/control validation.

## Sequence

- Sequence glob:
  `tools/yolo/workspace/dataset/images/0260701/20260701_154019_cam1_frame_*.jpg`
- Images matched: `452`
- Labeled GT boxes in the sequence: `52`
- Model: `artifacts/models/tennis_ball_yolo/model.pt`
- Device: CPU
- Threads: `10`
- Normal ROI: `960x540`
- Expanded ROI: `1280x720`
- Match IoU: `0.5`

## Replay Results

| Search imgsz | ROI imgsz | conf | search frames | ROI frames | expanded ROI | locks | lost | TP | FP | FN | recall | precision | median ms/img | p95 ms/img | est stereo FPS |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 320 | 320 | 0.05 | 411 | 41 | 15 | 4 | 4 | 13 | 27 | 39 | 0.250 | 0.325 | 9.52 | 11.40 | 52.54 |
| 416 | 320 | 0.05 | 290 | 162 | 66 | 28 | 28 | 30 | 117 | 22 | 0.577 | 0.204 | 18.12 | 21.53 | 27.59 |
| 512 | 320 | 0.05 | 170 | 282 | 152 | 65 | 65 | 29 | 222 | 23 | 0.558 | 0.116 | 11.94 | 23.63 | 41.89 |
| 512 | 320 | 0.15 | 304 | 148 | 83 | 41 | 41 | 17 | 61 | 35 | 0.327 | 0.218 | 18.84 | 24.45 | 26.53 |
| 416 | 320 | 0.15 | 373 | 79 | 32 | 15 | 15 | 17 | 40 | 35 | 0.327 | 0.298 | 18.80 | 23.97 | 26.59 |

## Readout

Stateful ROI can run fast when it spends most frames in ROI mode:

- `search=512 / roi=320 / conf=0.05` reached an estimated `41.89` stereo FPS.
- But precision was poor (`0.116`), meaning the current model often locks or
  updates on false positives.

Full-frame search at low `imgsz` is the weak entry point:

- `search=320` is fast but stays in `SEARCH` for `411 / 452` frames and recall is
  only `0.250`.
- `search=416` improves recall to `0.577` at low threshold, but estimated stereo
  FPS falls below `30`.
- `search=512` finds more candidates and spends more frames in ROI mode, but low
  threshold false positives make the lock unstable.

Raising confidence reduces false positives, but recall drops too much with the
current model. This points to model/data weakness, not state-machine cost.

## Training Decision

Do not train another full-frame low-`imgsz` model as the main fix. Full-frame
compression has already destroyed the far-ball signal before YOLO sees it.

First training target should be a **ROI/crop model**:

- Crop profile: `960x540`, with optional `768x432` hard case.
- Train/infer imgsz: start at `320`, compare `416`.
- Base: current `artifacts/models/tennis_ball_yolo/model.pt`, not scratch.
- Data: positive-jitter crops plus negatives from real labeled 4K frames.

The full-frame `SEARCH` model can be split later, but not first:

- A separate search model may be useful if it is trained for coarse high-recall
  full-frame acquisition.
- It can tolerate lower precision because stereo pairing and ROI confirmation can
  reject some false candidates.
- But it runs only while unlocked, so it should not dominate the initial training
  effort.

Recommended order:

1. Keep one model path for now.
2. Generate `960x540` ROI crop data.
3. Fine-tune current model on ROI crops.
4. Re-run `roi-track` replay.
5. Only if search remains the bottleneck, train a separate full-frame search
   model or add periodic higher-`imgsz` search.

## Answer To The Runtime Question

Small ROI can plausibly hit `40-50 FPS` stereo only when the tracker is already
locked and uses low `imgsz`. The current model does not yet keep that lock
cleanly enough.

Same-frame full search plus ROI is not the right runtime path. It behaves like a
two-pass detector and falls back toward `~15 FPS`.
