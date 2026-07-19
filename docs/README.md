# TennisBot 文档入口

日期：2026-07-08

## 先读这里

- [当前架构](current/architecture.md)
- [Vision Runtime](current/vision_runtime.md)
- [当前状态](current/status.md)
- [底盘 pose 输入缺口](current/chassis_pose_input_gap.md)
- [中文运行说明](current/how_to_run_zh.md)
- [命令入口使用说明](current/command_usage.md)
- [操作员运行手册](current/operator_runbook.md)
- [相机设备检查](current/camera_devices.md)
- [YOLO 检测 GUI](current/yolo_detect_gui.md)
- [YOLO ROI Runtime Search 计划](current/yolo_roi_runtime_search_plan_20260707.md)
- [YOLO 增强方案复盘](current/yolo_augmentation_scheme_review_20260707.md)
- [YOLO 固定曝光传统 ROI 数据集](current/yolo_fixed_exposure_traditional_roi_dataset_20260707.md)
- [YOLO 固定曝光传统 ROI 训练结果](current/yolo_fixed_exposure_traditional_roi_training_result_20260708.md)
- [YOLO 固定曝光 1024x576 单 ROI 训练结果](current/yolo_fixed_exposure_roi1024_training_result_20260708.md)
- [YOLO 固定曝光 1024x576 ROI imgsz960 训练结果](current/yolo_fixed_exposure_roi1024_imgsz960_training_result_20260708.md)
- [YOLO 自动曝光泛化性评估](current/yolo_auto_exposure_generalization_eval_20260708.md)
- [YOLO Final Raw Benchmark v1 计划](current/yolo_final_raw_benchmark_v1_plan_20260708.md)
- [YOLO Final Raw Benchmark packaged baseline](current/yolo_final_raw_baseline_model_pt_fullframe_imgsz960_eval_20260708.md)
- [YOLO Final Train-Pool ROI/Full 数据集计划](current/yolo_final_trainpool_roi_full_dataset_plan_20260708.md)

## 工具入口

- [标定工具](../tools/calibration/README.md)
- [YOLO 工具](../tools/yolo/README.md)
- [录制工具](../tools/recording/README.md)

## 报告

- [2026-06-15 至 2026-06-28 双周业务报告](reports/biweekly_report_20260615_20260628.md)

报告图片和生成资产放在 `reports/assets/`。

## 归档

历史计划、实验、探针、评审和迁移记录放在 `archive/YYYYMMDD/`。

常见分类：

- `plans/`
- `results/`
- `audits/`
- `calibration/`
- `migrations/`
- `probes/`
- `refactor/`
- `yolo/`

## 写文档规则

`docs/` 根目录只保留入口文档。当前事实放在 `docs/current/`，正式报告放在
`docs/reports/`，计划、实验结果和历史记录放在 `docs/archive/YYYYMMDD/`。
