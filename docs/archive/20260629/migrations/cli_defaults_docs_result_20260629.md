# 命令默认值和中文入口文档结果

日期：2026-06-29

## 结果

已给主要操作入口补齐默认值说明和中文使用文档：

- `tools/yolo`
- `tools/calibration`
- `apps/live3d`
- 根目录 `scripts/*.ts`
- `docs/current/command_usage.md`

## 代码改动

- 给以下命令补默认模型包路径：
  - `tennisbot-yolo package create`
  - `tennisbot-yolo package verify`
- 把默认生成报告路径改到日期归档目录：
  - `docs/archive/YYYYMMDD/probes/local_runtime_preflight_YYYYMMDD.md`
  - `docs/archive/YYYYMMDD/probes/local_physical_validation_status_YYYYMMDD.md`
  - `docs/archive/YYYYMMDD/calibration/calibration_target_print_check_YYYYMMDD.md`
- 主要命令的 `--help` 现在会显示默认值，并尽量使用中文说明。

## 特意保留的例外

`scripts/record-target-print-check.ts --measured-square-mm` 仍然没有默认值。
这是人工实测的物理打印尺寸，必须显式传入，避免生成假的验收证据。

## 验证

- `uv run --no-sync python -m camera_calib_lab.cli capture charuco-auto-gui --help`
- `uv run --no-sync python -m camera_calib_lab.cli capture stereo-charuco-auto-gui --help`
- `uv run --no-sync python -m tennisbot_yolo.cli annotate --help`
- `uv run --no-sync python -m tennisbot_yolo.cli package create --help`
- `uv run --no-sync python -m tennisbot_yolo.cli package verify --help`
- `uv run --no-sync python -m tennisbot_yolo.cli detect-gui --help`
- `uv run --no-sync python -m tennisbot_yolo.cli detect-gui --dry-run`
- `uv run --no-sync pytest -q` in `tools/yolo`: 14 passed
- `uv run --no-sync python -m compileall src/camera_calib_lab`
- `uv run --no-sync python -m compileall src/tennisbot_yolo`
- `bun scripts/check-camera-brightness.ts --help`
- `bun scripts/start-local-runtime.ts --help`
- `bun scripts/operator-preflight.ts --help`
- `bun scripts/physical-validation-status.ts --help`
- `bun scripts/record-target-print-check.ts --help`
- `bun test` in `apps/live3d`: 45 passed
- `bun run typecheck` in `apps/live3d`
- `bun run build` in `apps/live3d`
- `bun scripts/physical-validation-status.ts --output /tmp/tennisbot_physical_validation_status_check.md --output-json /tmp/tennisbot_physical_validation_status_check.json`
  按预期非零退出，因为物理验收门槛还没全部完成；脚本成功写出 Markdown 和
  JSON 报告。
- `git diff --check`
