# 模型 artifact 上传计划

日期：2026-06-29

## 目标

把当前可用的 YOLO 运行时模型包提交到 GitHub，使新环境可以直接拉取模型包运行
默认检测流程。

## 范围

- 只放行 `artifacts/models/tennis_ball_yolo/**`。
- 保持其它 `artifacts/` 内容忽略，避免误提交训练缓存、采集数据或大文件。
- 提交模型包内的 `.pt`、`.onnx` 和运行时元数据。
- 提交前验证模型包合同。

## 当前大小

- `model.pt`: about 5.2 MB
- `model.onnx`: about 9.8 MB
- package total: about 16 MB

## 验证

- `uv run --no-sync tennisbot-yolo package verify`
- `git diff --check`
