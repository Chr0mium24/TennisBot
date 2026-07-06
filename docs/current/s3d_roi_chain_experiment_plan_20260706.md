# S3d ROI Chain Experiment Plan - 2026-07-06

## Goal

Measure whether the current S3d temporal heatmap search output can feed ROI YOLO without losing most of the detector recall.

## Scope

This is an offline replay on saved monocular frames from `20260701_155008`.
It does not validate ROS/Gazebo, stereo triangulation, target prediction, or chassis control.

## Chain

1. Run S3d full-frame temporal heatmap search on a five-frame window.
2. Convert the heatmap peak to the original frame coordinate.
3. Crop a `960x540` ROI around the S3d peak.
4. Run ROI YOLO at `imgsz=320`.
5. Compare the final YOLO boxes with the existing labels.

## Metrics

- S3d search recall at threshold `0.40` and radius `12px` on the S3d `960x540` input scale.
- ROI contains rate after S3d true-positive search.
- ROI YOLO conditional recall on S3d true-positive crops.
- Full-chain final recall and precision.
- Per-camera median S3d, ROI YOLO, and combined latency.

## Command

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

## Decision Rule

If ROI YOLO conditional recall is high while final recall stays near S3d recall, the bottleneck is S3d search/localization.
If ROI YOLO conditional recall is low, fix the ROI detector/crop before runtime integration.
