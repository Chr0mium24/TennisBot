# S3d Search + ROI YOLO Chain Result - 2026-07-06

## Scope

This is an offline monocular replay of `S3d full-frame temporal heatmap search -> ROI crop -> ROI YOLO refinement`.
It does not use real ROS/chassis, camera capture, stereo triangulation, target prediction, or chassis control.
It answers whether the current S3d search output can feed the existing ROI YOLO detector without losing most recall.

## Settings

- S3d checkpoint: `tools/yolo/workspace/runs/temporal_heatmap/search_small_heatmap_w5_480x270_pseudo989_synth500_20260706/best_recall.pt`
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
| cam1 | 424 | 49 | 35/385/14 | 0.714 | 35/35 (1.000) | 0.943 | 33/103/16 | 0.673 | 0.243 | 85.16 | 6.71 | 94.21 | 5.31 |
| cam2 | 434 | 44 | 32/399/12 | 0.727 | 32/32 (1.000) | 1.000 | 32/134/12 | 0.727 | 0.193 | 67.66 | 5.75 | 75.42 | 6.63 |

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
