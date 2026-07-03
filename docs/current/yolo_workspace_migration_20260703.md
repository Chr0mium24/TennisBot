# YOLO Workspace Migration

日期：2026-07-03

## 目标

移除 `tools/yolo/yolo` 套娃目录，把 YOLO 工具的本地数据和运行输出统一到
`tools/yolo/workspace`。不保留旧路径兼容入口。

## 计划

1. 将 annotator server 从 `tools/yolo/yolo/scripts/serve_annotator.py` 移到
   `tennisbot_yolo` 包内。
2. 让 `tennisbot-yolo annotate` 直接调用包内 server，不再 subprocess 到旧脚本。
3. 把默认 dataset、excluded file、sprite runs 和 copy-paste 输出路径改为
   `tools/yolo/workspace/...`。
4. 将本地旧 `tools/yolo/yolo/runs` 移到 `tools/yolo/workspace/runs`。
5. 删除空的旧 `tools/yolo/yolo` 目录。
6. 更新 README、命令文档、增强配置和 ignore 规则。

## 结果

- 新包内 annotator 模块为 `tools/yolo/src/tennisbot_yolo/annotator.py`。
- 共享默认路径集中在 `tools/yolo/src/tennisbot_yolo/paths.py`。
- 默认数据目录为 `tools/yolo/workspace/dataset`。
- 默认运行输出目录为 `tools/yolo/workspace/runs`。
- 本地 sprite 候选已从旧 runs 目录移动到 `tools/yolo/workspace/runs/sprites`。
- `tools/yolo/yolo` 目录已从工作区删除。

## 验证结果

```bash
rg -n "tools/yolo/yolo|TOOL_ROOT / \"yolo\"|/yolo/dataset|yolo/runs|ANNOTATOR_SCRIPT|serve_annotator\\.py" tools/yolo scripts/yolo.ts docs/current .gitignore -g '!docs/current/yolo_workspace_migration_20260703.md' -g '!tools/yolo/MIGRATION_CHECKLIST.md' -g '!**/__pycache__/**' -g '!**/node_modules/**'
cd tools/yolo && uv run pytest -q
uv run --project tools/yolo tennisbot-yolo annotate --help
uv run --project tools/yolo --extra augment tennisbot-yolo sprites extract --help
uv run --project tools/yolo --extra augment tennisbot-yolo sprites review --help
uv run --project tools/yolo --extra augment tennisbot-yolo augment copy-paste --help
bun scripts/yolo.ts --help
uv run --project tools/yolo python -m compileall -q tools/yolo/src
```

- 排除本迁移记录和旧 Lab 迁移 checklist 后，旧 `tools/yolo/yolo` 路径无残留。
- `tools/yolo` 测试通过：`20 passed`。
- `annotate`、`sprites extract`、`sprites review` 的默认路径均指向
  `tools/yolo/workspace`。
- `bun scripts/yolo.ts --help` 已显示新的 workspace 默认路径。
- Python compileall 通过。
