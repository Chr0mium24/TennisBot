# 命令默认值和中文入口文档计划

日期：2026-06-29

## 目标

让面向操作员的命令入口具备清楚的默认值，并补齐中文使用说明。

## 范围

- 给缺失默认值的路径类 CLI 参数补默认值。
- 真实物理测量值不伪造默认值，必须人工显式输入。
- 生成的 Markdown 报告默认写入 `docs/archive/YYYYMMDD/...`。
- 给根脚本、标定工具、YOLO 工具和 Live3D 增加中文入口文档。
- 不改变检测、标定、三角化或预测算法行为。

## 验证

- 用 `uv` 检查 Python CLI help、dry-run 和测试。
- 用 `bun` 检查 TypeScript help、typecheck、build 和测试。
- 运行 `git diff --check`。
