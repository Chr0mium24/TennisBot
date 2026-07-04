# Search-S2 Teacher Result - 2026-07-04

## Scope

This experiment follows the research decision in
`docs/current/yolo_search_model_research_decision_20260704.md`: train a
pretrained YOLOv8n-P2 full-frame teacher before doing more architecture edits.

This is offline monocular replay only. It does not validate ROS/Gazebo stereo
triangulation, target prediction, or chassis control.

## Model

| Field | Value |
|---|---|
| Run | `search_s2_teacher_yolov8n_p2_fullframe_imgsz640_20260704` |
| Architecture | `tools/yolo/configs/tennis_yolov8n_p2.yaml` |
| Init | `yolov8n.pt` partial transfer |
| Heads | P2/P3/P4/P5 |
| Train data | `search_fullframe_s1b_hardneg_20260704` |
| Train images | 332 images, including 175 backgrounds |
| Val images | 104 images, including 52 backgrounds |
| Train imgsz | 640 |
| Parameters | 2.92M fused |
| FLOPs | 12.2 GFLOPs fused |

## Training Result

Training stopped early after 59 epochs. Best checkpoint was epoch 47.

| checkpoint | epoch | precision | recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|---:|
| best mAP50 | 47 | 0.32156 | 0.07692 | 0.07903 | 0.02350 |
| best recall | 45 | 0.46496 | 0.07692 | 0.06833 | 0.01967 |
| last | 59 | 0.43069 | 0.07692 | 0.07145 | 0.02194 |

The teacher did not become high recall. Validation recall is roughly 4/52
objects, so it is not suitable for pseudo-label mining or runtime promotion.

## Continuous Replay Result

Held-out sequence:

- `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam1_frame_*.jpg`
- `tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam2_frame_*.jpg`

Stateful ROI settings:

- search imgsz 640
- locked ROI 960x540 at imgsz 320
- expanded ROI 1280x720
- lost after 3 misses
- expand after 1 miss
- edge margin ratio 0.20
- CPU, 10 torch threads

| Search model | ROI model | Camera | Images | GT | TP | FP | FN | Recall | Precision | Search frames | ROI frames | Expanded ROI | Median ms/img | Est stereo FPS | Detail |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| S2 P2 | S2 P2 | cam1 | 124 | 49 | 9 | 10 | 40 | 0.184 | 0.474 | 96 | 28 | 16 | 36.85 | 13.57 | `docs/current/yolo_search_s2_teacher_sequence_155008_cam1_labeled_window_20260704.md` |
| S2 P2 | S2 P2 | cam2 | 134 | 44 | 9 | 18 | 35 | 0.205 | 0.333 | 99 | 35 | 19 | 44.02 | 11.36 | `docs/current/yolo_search_s2_teacher_sequence_155008_cam2_labeled_window_20260704.md` |
| S2 P2 | ROI crop | cam1 | 124 | 49 | 9 | 5 | 40 | 0.184 | 0.643 | 100 | 24 | 12 | 35.89 | 13.93 | `docs/current/yolo_search_s2_teacher_roi_crop_sequence_155008_cam1_labeled_window_20260704.md` |
| S2 P2 | ROI crop | cam2 | 134 | 44 | 9 | 9 | 35 | 0.205 | 0.500 | 106 | 28 | 15 | 36.66 | 13.64 | `docs/current/yolo_search_s2_teacher_roi_crop_sequence_155008_cam2_labeled_window_20260704.md` |

## Decision

Do not promote Search-S2.

Findings:

- The ROI crop model reduces false positives once locked, but it cannot recover
  balls that the full-frame search model never acquires.
- The tracker remains in full-frame search for most frames. That keeps the CPU
  frame rate around 11-14 estimated stereo FPS, below the intended ROI runtime.
- The failure is not fixed by a bigger ROI window. Bigger windows make the
  search/ROI cost worse and still do not recreate missing ball pixels.
- If the ball is compressed to only a few weak pixels or blurred away, a
  single-frame box detector cannot learn information that is absent in the
  image. The next model has to use temporal context and point/heatmap labels,
  matching TrackNet/WASB-style sports-ball detectors.

## Next Step

Build `Search-S3 Temporal Heatmap Teacher`:

- input: 3 consecutive frames, aligned at full-frame search resolution;
- target: Gaussian heatmap at the ball center, derived from YOLO box centers;
- model role: offline/high-recall search-acquisition teacher, not immediate CPU
  runtime;
- training data: continuous labeled sequences excluding `20260701_155008`;
- evaluation: same held-out `155008` replay after converting heatmap peaks to
  boxes/centers;
- promotion path: use S3 to mine positives and then distill a smaller runtime
  search model only after S3 recall is high.

Before training S3, audit the sequence labels and camera balance. The current
full-frame data is heavily cam1-biased, and the Search-S2 results show that
more same-format YOLO training is not the next useful experiment.
