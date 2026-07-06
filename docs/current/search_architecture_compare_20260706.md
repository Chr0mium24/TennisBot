# Search Architecture Compare - 2026-07-06

## Scope

This compares the available search/acquisition evidence on the same labeled continuous sequence where possible:

`tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`

This is an offline detector comparison. It does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Commands

YOLO full-frame search baseline:

```bash
find tools/yolo/workspace/dataset/images/0260701 -maxdepth 1 -type f \
  -name '20260701_155008_cam*_frame_*.jpg' | sort > /tmp/tennisbot_155008_samples.txt

uv run --project tools/yolo --extra detect tennisbot-yolo benchmark roi-sample \
  --sample-list /tmp/tennisbot_155008_samples.txt \
  --sample-limit 0 \
  --full-imgsz-values 320,416,512,640 \
  --roi-profile roi_960x540_320:960:540:320 \
  --coarse-imgsz 416 \
  --device 0 \
  --threads 0 \
  --conf 0.05 \
  --iou 0.7 \
  --match-iou 0.5 \
  --max-detections 300 \
  --output-markdown docs/current/yolo_fullscreen_155008_search_compare_20260706.md
```

S3d search plus ROI YOLO:

```bash
uv run --project tools/yolo --extra detect tennisbot-yolo benchmark s3d-roi-chain \
  --checkpoint tools/yolo/workspace/runs/temporal_heatmap/search_s3d_temporal_heatmap_w5_960x540_pseudo989_synth500_20260705/best_recall.pt \
  --roi-model tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt \
  --sequence-glob "tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg" \
  --roi-width 960 \
  --roi-height 540 \
  --roi-imgsz 320 \
  --threshold 0.40 \
  --radius-px 12 \
  --s3d-device auto \
  --yolo-device 0 \
  --output-markdown docs/current/s3d_roi_chain_experiment_result_20260706.md
```

## Current Results

### Full-Frame YOLO Search

Same 866-frame `155008` sample list, `93` labeled positives.

| model/path | mode | imgsz | TP | FP | FN | recall | precision | median ms/img | est stereo FPS |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| old YOLO | full-frame | 320 | 21 | 694 | 72 | 0.226 | 0.029 | 4.17 | 119.79 |
| old YOLO | full-frame | 416 | 27 | 424 | 66 | 0.290 | 0.060 | 4.39 | 113.94 |
| old YOLO | full-frame | 512 | 31 | 321 | 62 | 0.333 | 0.088 | 4.65 | 107.56 |
| old YOLO | full-frame | 640 | 37 | 509 | 56 | 0.398 | 0.068 | 5.17 | 96.78 |

### S3d Search + ROI YOLO

Same sequence, but S3d uses a five-frame window, so scored frames are `424` for cam1 and `434` for cam2.

| camera | S3d TP/FP/FN | S3d recall | ROI contains | ROI YOLO conditional recall | final TP/FP/FN | final recall | final precision | total ms/img | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 39/351/10 | 0.796 | 39/39 | 0.949 | 37/145/12 | 0.755 | 0.203 | 100.56 | 4.97 |
| cam2 | 33/385/11 | 0.750 | 33/33 | 1.000 | 33/140/11 | 0.750 | 0.191 | 100.61 | 4.97 |

S3d cost dominates:

| component | median ms/img |
|---|---:|
| S3d full-frame heatmap | ~95.96 |
| ROI YOLO crop | ~4.82 |

## Readout

YOLO full-frame is fast but misses too much. Increasing `imgsz` from `320` to `640` only raises recall from `0.226` to `0.398`, still far below the target and with poor precision.

S3d search has much better recall than full-frame YOLO, but it is far too slow in the current implementation. Its false-positive count is also high, which causes many background ROI calls.

ROI YOLO is not the main bottleneck after search is correct. When S3d finds the right area, ROI YOLO recall is `0.949` on cam1 and `1.000` on cam2.

## Architecture Decision

Do not put current S3d directly into runtime as the final search model. It is a useful teacher and proof that temporal heatmap search can find more balls than full-frame YOLO, but it does not meet the FPS target.

Do not rely on the current full-frame YOLO as the main search model. It is fast enough, but recall is too low even at `imgsz=640`.

The next fair experiment should compare two small runtime students:

| candidate | input | output | purpose | risk |
|---|---|---|---|---|
| YOLO search student | full-frame/tiled, P2 or crop-aware | bbox | preserve runtime compatibility | small ball may still vanish after resize |
| small heatmap search student | lower-res frame or motion input | coarse ball center | minimal output for acquisition | needs new training/export/runtime adapter |

Use S3d and labels as teachers for the heatmap student, and keep ROI YOLO for locked/refinement mode unless ROI-specific tests regress.

## Immediate Next Step

Train or prototype a small heatmap student only if it is explicitly constrained for runtime:

- target input: `480x270` or `640x360`, not current `960x540`;
- input frames: start with `1` and `3`, not five frames by default;
- output: single-channel coarse heatmap;
- success condition: recall clearly above full-frame YOLO `0.398` while keeping estimated stereo FPS near or above the locked ROI target.

In parallel, a YOLO search student should be evaluated only with a configuration that preserves the small ball signal, such as tiled input or a P2 head. A plain full-frame low-`imgsz` YOLO student is unlikely to solve the search problem.
