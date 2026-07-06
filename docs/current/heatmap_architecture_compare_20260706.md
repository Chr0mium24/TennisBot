# Heatmap Architecture Compare - 2026-07-06

## Scope

This note compares heatmap-style search/acquisition models for TennisBot ball
localization. It covers:

- measured local experiments already run in this project;
- candidate CNN heatmap architectures worth testing next;
- what should and should not be promoted into the runtime chain.

It does not claim ROS/Gazebo catch-loop validation.

## Current Implemented Heatmap Model

The current `tennisbot-yolo temporal-heatmap train` command builds one model
family only: `TinyTemporalHeatmapNet`.

Architecture summary:

- input: odd temporal RGB window, usually 3 or 5 frames;
- encoder: two downsampling stages;
- decoder: bilinear upsampling with skip connections;
- output: single-channel ball-center heatmap at input resolution;
- postprocess: take heatmap peak as `(x, y, score)`.

This is closer to a tiny U-Net/TrackNet-style heatmap model than YOLO. It is
not S3D in the original video-classification sense; the local name `S3d` refers
to this project's Search-S3d experiment.

## Measured Project Results

The following rows are not a fair architecture-only sweep because the data,
input size, and temporal window changed across experiments. They are still the
best evidence currently available in this repository.

| Model | Architecture family | Window | Input | Extra data | Best recall | Precision at best recall | Median latency | Est stereo FPS | Status |
|---|---|---:|---|---|---:|---:|---:|---:|---|
| S3 | Tiny temporal U-Net heatmap | 3 | 640x360 | none | 0.462 | 0.741 | not repeated here | 55.43 GPU | obsolete baseline |
| S3b | Tiny temporal U-Net heatmap | 5 | 960x540 | none | 0.613 | 0.350 | not repeated here | 21.41 GPU | teacher baseline |
| S3c | Tiny temporal U-Net heatmap | 5 | 960x540 | 500 synthetic | 0.699 | 0.283 | not repeated here | not listed | better recall |
| S3d | Tiny temporal U-Net heatmap | 5 | 960x540 | 989 pseudo + 500 synthetic | 0.774 | 0.327 | 23.27 ms training latency; about 96 ms in current chain replay | 21.48 training estimate; about 5 chain FPS | best recall teacher, too slow/noisy for runtime |
| Small heatmap | Tiny temporal U-Net heatmap | 5 | 480x270 | pseudo root + 500 synthetic | 0.720 | 0.293 | 4.74 ms | 105.43 | best runtime-speed candidate so far |

Comparison against YOLO search baselines:

| Model | Input | Recall | Precision | Median latency | Est stereo FPS | Meaning |
|---|---|---:|---:|---:|---:|---|
| Old YOLO full-frame | 640 | 0.398 | 0.068 | 5.17 ms | 96.78 | fast but low recall |
| YOLO micro P2/no-P5 | 640 | 0.215 | 0.235 | 5.05 ms | 99.07 | smaller YOLO did not fix recall |
| Small heatmap | 480x270 x 5 frames | 0.720 | 0.293 | 4.74 ms | 105.43 | better search candidate |

## Candidate Heatmap Architectures

| Candidate | Input | Core idea | Expected speed | Expected recall | Implementation cost | Fit for TennisBot |
|---|---|---|---|---|---|---|
| Tiny temporal U-Net, current | 3/5 RGB frames | shallow encoder-decoder with skips | very fast at 480x270; moderate at 960x540 | already 0.720-0.774 | already implemented | keep as baseline |
| Tiny temporal U-Net 640x360 | 3/5 RGB frames | same model, higher input than 480x270 | likely 7-12 ms per cam depending GPU | should recover some small-ball information | no architecture change | first next experiment |
| TrackNet-style encoder-decoder | stacked frames | deeper U-Net-like ball heatmap network | slower than current tiny model | potentially better trajectory-aware recall | moderate | strong candidate if small variant is used |
| MobileNetV3-FPN heatmap | 3/5 RGB frames | efficient backbone + multi-scale FPN decoder | fast | likely better feature extraction than current tiny encoder | moderate | best student architecture candidate |
| ShuffleNetV2/GhostNet heatmap | 3/5 RGB frames | very cheap backbone + light decoder | fastest | may lose recall if too narrow | moderate | speed ceiling test |
| CenterNet-style point heatmap | single or temporal frames | keypoint heatmap, optional offset regression | fast to moderate | good for point localization, weaker without temporal input | moderate | useful if adding offset head |
| HRNet-lite heatmap | 3/5 RGB frames | keeps high-resolution branch throughout | slower | good small-object localization | higher | accuracy candidate, probably not runtime first |
| ConvLSTM heatmap | temporal features | recurrent feature fusion | slower and stateful | may help tracking/occlusion | high | not first choice for runtime |
| 3D CNN heatmap | temporal volume | spatiotemporal convolutions | usually slower | can learn motion cues | high | likely too heavy unless very small |

## Architecture Conclusions

1. The current best evidence favors heatmap search over full-frame YOLO for this
   task. The small heatmap model got much higher held-out recall than both YOLO
   baselines at similar measured latency.
2. The current comparison is not yet a pure backbone comparison. Most S3/S3b/S3c
   differences came from window size, resolution, pseudo labels, and synthetic
   data.
3. Lowering input to `480x270` can lose small-ball pixels. The fact that the
   small heatmap still worked better than YOLO suggests temporal heatmap output
   is the right formulation, not that `480x270` is the final input.
4. For runtime, the most practical next architecture is not a heavier S3d. It is
   a small temporal heatmap student at `640x360`, followed by ROI confirmation.
5. If `640x360` current-tiny heatmap is not enough, the next architecture to add
   should be `MobileNetV3-small + FPN heatmap`, not another smaller YOLO.

## Recommended Next Sweep

Run a fair heatmap architecture sweep with the same labels, validation sequence,
epochs, thresholds, and latency measurement.

| Priority | Model | Window | Input | Purpose |
|---:|---|---:|---|---|
| 1 | current tiny temporal U-Net | 5 | 640x360 | isolate resolution effect vs 480x270 |
| 2 | current tiny temporal U-Net | 3 | 640x360 | test whether 3 frames reduce latency/buffer cost without losing much recall |
| 3 | MobileNetV3-small FPN heatmap | 5 | 640x360 | test better lightweight features |
| 4 | ShuffleNetV2/GhostNet heatmap | 5 | 640x360 | test fastest deployable backbone |
| 5 | TrackNet-lite | 5 | 640x360 | test stronger tennis-specific heatmap baseline |

Promotion rule:

- Search model candidate: recall should clearly exceed YOLO full-frame recall
  and ideally exceed `0.80` on `20260701_155008`.
- Runtime candidate: total stereo search latency should leave budget for ROI
  YOLO/stereo, so the search model should be near or below `8-10 ms` per camera
  on the target GPU.
- Teacher candidate: recall matters more than speed, but false positives must
  be audited before pseudo-label mining.

