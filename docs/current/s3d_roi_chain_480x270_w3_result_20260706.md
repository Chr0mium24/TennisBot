# S3d Search + ROI YOLO Chain Result - 2026-07-06

## Scope

This is an offline monocular replay of `S3d full-frame temporal heatmap search -> ROI crop -> ROI YOLO refinement`.
It does not use ROS/Gazebo, camera capture, stereo triangulation, target prediction, or chassis control.
It answers whether the current S3d search output can feed the existing ROI YOLO detector without losing most recall.

## Settings

- S3d checkpoint: `tools/yolo/workspace/runs/temporal_heatmap/search_small_heatmap_w3_480x270_pseudo989_synth500_20260706/best_recall.pt`
- ROI YOLO model: `tools/yolo/workspace/runs/training/roi_crop_960x540_teacher_imgsz320_20260704/weights/best.pt`
- Sequence glob: `/home/cr/Codes/TennisBot/tools/yolo/workspace/dataset/images/0260701/20260701_155008_cam*_frame_*.jpg`
- ROI crop: `960x540`
- ROI YOLO imgsz: `320`
- S3d threshold: `0.4`
- S3d hit radius: `6.0` px at S3d input scale
- YOLO confidence: `0.05`
- YOLO prediction IoU: `0.7`
- YOLO match IoU: `0.5`
- S3d device: `cuda:0`
- YOLO device: ``
- CUDA available: `True`
- Torch: `2.12.1+cu130`

## Results

| camera | frames | positives | S3d TP/FP/FN | S3d recall | ROI contains | ROI YOLO cond recall | final TP/FP/FN | final recall | final precision | S3d ms | ROI YOLO ms | total ms | est stereo FPS |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| cam1 | 426 | 49 | 34/392/15 | 0.694 | 34/34 (1.000) | 0.941 | 32/105/17 | 0.653 | 0.234 | 22.87 | 4.66 | 27.57 | 18.14 |
| cam2 | 436 | 44 | 32/404/12 | 0.727 | 32/32 (1.000) | 1.000 | 32/138/12 | 0.727 | 0.188 | 22.89 | 4.68 | 27.60 | 18.12 |

## Metric Definitions

- `S3d recall` counts a positive frame as found only when the heatmap peak is above threshold and within the radius of the labeled ball center.
- `ROI contains` counts S3d true positives whose crop contains the labeled ball center before YOLO refinement.
- `ROI YOLO cond recall` is ROI YOLO recall only on frames where S3d was a true positive and the ROI contained the ball center.
- `final recall` is the full chain recall against all labeled positives in that camera sequence.
- `est stereo FPS` assumes the same per-camera median cost is paid sequentially for left and right images.

## Readout

- If `ROI YOLO cond recall` is high but `final recall` is limited, the bottleneck is S3d search/localization.
- If `ROI YOLO cond recall` is low, the ROI detector or crop size needs work before runtime integration.
- This experiment still does not prove real stereo runtime; it only validates the detector chain on saved frames.
