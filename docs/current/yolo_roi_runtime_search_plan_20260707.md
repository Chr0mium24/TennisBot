# YOLO ROI Runtime Search Plan - 2026-07-07

## Scope

This plan turns the current offline YOLO/ROI evidence into a runtime direction.
It is a plan, not a completed ROS/Gazebo catch-loop validation.

The goal is:

```text
fast reacquisition/search -> crop ROI -> YOLO verify/refine -> stereo match -> trajectory/runtime
```

The immediate goal is not to train another small full-frame model. The first
runtime step should prove that ROI-first detection works with the existing
stereo runtime and real camera frames.

## Decision

Do not rely on a low-resolution full-frame small model to find the ball.

Reason:

- If a tennis ball has already been downscaled to one pixel or less, a small
  model cannot recover the missing signal.
- Previous full-frame YOLO search experiments were fast but low recall on the
  held-out `20260701_155008` sequence.
- Previous ROI crop experiments showed the useful direction: crop before YOLO
  resize, then run detection inside the crop.

Use the existing YOLO model or ROI-crop model as the confirmation/refinement
detector. Add a small search model only after the ROI runtime path works, and
only if that small model either sees high-resolution tiles or uses temporal
information without erasing the ball.

## Runtime State Machine

Each camera keeps a lightweight detector state:

- `mode`: `LOCKED`, `EXPANDED_ROI`, or `SEARCH`;
- last accepted detection center and box;
- pixel velocity estimated from recent accepted detections;
- miss count;
- near-edge count;
- current ROI window.

The stereo matcher remains the authority for accepting a pair. Monocular
detections can propose ROI updates, but the runtime should only fully trust a
lock after left/right detections pass stereo geometry and depth checks.

### LOCKED

When the previous stereo frame produced an accepted ball match:

1. Predict the next left/right image centers from the previous accepted centers
   plus pixel velocity.
2. Crop a normal ROI around each predicted center.
3. Run YOLO on the ROI, not on the full frame.
4. Offset the ROI detections back into full-frame coordinates.
5. Run the existing stereo matcher.
6. If stereo accepts the match, update ROI state and stay `LOCKED`.

Initial ROI sizes to test:

| name | crop | YOLO imgsz | purpose |
|---|---:|---:|---|
| normal | `960x540` | `320` or `416` | fast locked tracking |
| square-1k | `1024x1024` | `416` | safer vertical margin |

### EXPANDED_ROI

Enter this mode when:

- the normal ROI misses;
- the best detection is near the ROI edge;
- velocity predicts the ball may leave the normal crop.

Use a larger crop for one or a few frames, then fall back to `LOCKED` on a
valid stereo match.

Initial expanded ROI sizes to test:

| name | crop | YOLO imgsz | purpose |
|---|---:|---:|---|
| expanded | `1280x720` | `416` | recover modest prediction error |
| large | `1536x864` | `512` | recover larger miss before full search |

### SEARCH

Enter this mode when:

- startup has no lock;
- the expanded ROI misses for the configured limit;
- stereo rejects too many candidate pairs.

Do not shrink the whole 4K image into a tiny full-frame input as the primary
search path. Use high-resolution tiled search.

For `3840x2160`, a true `1K` window does not cover the screen with 4 crops. A
`1024`-level grid needs roughly 4 columns by 3 rows before overlap. Four-crop
coverage requires larger tiles, such as the existing `2048x1216` profile.

Initial search profiles:

| profile | tiles/camera | crop | overlap | note |
|---|---:|---:|---:|---|
| fast-4tile | 4 | `2048x1216` | `160` | existing practical 4K tiled search profile |
| 1k-grid | 12+ | about `1024` | `128-192` | preserves more detail, much more expensive |

Search outputs are candidate centers. Each candidate must be confirmed by ROI
YOLO and stereo matching before the runtime enters `LOCKED`.

## Small Model Policy

Do not block the ROI runtime on a new small model.

A small model is useful only as a future search accelerator if it satisfies one
of these constraints:

1. It runs on high-resolution tiles, so the ball is still visible.
2. It uses temporal evidence to recover weak moving-ball signals.
3. It outputs coarse candidate centers and then lets ROI YOLO plus stereo
   geometry confirm the result.

Do not promote a small full-frame low-resolution detector just because it is
fast. Its recall must be measured after ROI confirmation and stereo pairing.

## Implementation Plan

### Step 1: Offline replay adapter

Extend the existing stateful ROI replay into the stereo detector shape used by
`YoloBallDetector.detect_pair`.

Expected behavior:

- accept left/right frames;
- choose per-camera ROI or search tiles from detector state;
- return full-frame `BallDetection` objects;
- expose diagnostics for mode, ROI crop, search tile count, miss count, and
  selected candidate.

This should remain a detector implementation, not a local catch-loop substitute.

### Step 2: Runtime integration behind explicit parameters

Add runtime parameters with conservative defaults:

```text
yolo_roi_mode: false
yolo_roi_width: 960
yolo_roi_height: 540
yolo_roi_imgsz: 320
yolo_expanded_roi_width: 1280
yolo_expanded_roi_height: 720
yolo_search_tile_width: 2048
yolo_search_tile_height: 1216
yolo_search_tile_overlap: 160
yolo_max_locked_misses: 2
yolo_max_expanded_misses: 2
```

The default runtime must remain compatible with the current detector path until
the ROI mode is explicitly enabled.

### Step 3: Validation

Offline validation:

- replay saved left/right sequences;
- report detection recall/precision before stereo and after stereo;
- report mode counts: locked ROI, expanded ROI, search;
- report median/p95 detector latency per camera and per stereo frame;
- write results to `docs/current/*.md`.

Hardware validation:

- run real cameras with runtime logging enabled;
- inspect `detections.ndjson`, `observations.ndjson`, and `targets.ndjson`;
- verify that accepted points are transformed into field/interface coordinates
  before trajectory fitting;
- verify `/target/raw` timing only with real chassis pose input.

No result should claim a real catch-loop validation unless ROS/Gazebo or the
real backend pose/control chain is active.

## Promotion Criteria

Promote stateful ROI mode only if:

- locked ROI conditional recall stays high on saved replay and live camera logs;
- search/reacquisition does not dominate the frame budget;
- stereo matching rejects false positives without destroying true positives;
- detector latency leaves room for trajectory prediction and ROS publishing;
- diagnostics clearly show when the runtime is locked, expanded, or searching.

Target first milestone:

| metric | target |
|---|---:|
| locked ROI YOLO conditional recall | `>= 0.90` |
| locked ROI stereo detector budget | near `30 FPS` stereo or better |
| search fallback | correct but allowed to be slower |
| runtime mode | explicit opt-in |

## Non-Goals

- Do not add a local fake car tracker or fake catch substitute for no-ROS tests.
- Do not claim real catch-loop completion from offline replay.
- Do not convert coordinates only at `/target/raw`; runtime observations and
  trajectory history must stay in field/interface coordinates after the camera
  point is transformed.
- Do not make a small full-frame low-resolution model a required dependency for
  the first ROI runtime landing.
