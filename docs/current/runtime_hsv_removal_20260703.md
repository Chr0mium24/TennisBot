# Runtime HSV Removal

日期：2026-07-03

## 目标

移除 stereo/headless 运行时链路里的 HSV 检测器、CLI 参数、配置参数、
测试和文档入口，收敛到 YOLO 作为唯一运行时球检测路径。

## 计划

1. 搜索 stereo/headless/runtime docs 中的 HSV、`--detector` 和 `hsv_*` 引用。
2. 删除 `tools/stereo` 的 `HsvBallDetector` 与 HSV mask 工具函数。
3. 删除 stereo GUI 的 `--detector` 和 `--hsv-*` CLI 参数。
4. 删除 headless ROS node 的 `detector` 和 `hsv_*` 参数，固定构造 YOLO detector。
5. 删除 HSV detector 单测与文档示例。
6. 运行搜索、Python 测试和 Bun wrapper 检查确认入口已清理。

## 结果

- `tools/stereo` 现在只暴露 YOLO 运行时检测器。
- `bun scripts/stereo.ts gui` 非 dry-run/help 路径始终使用 `uv --extra detect`。
- `src/tennisbot_headless_vision` 配置不再声明 `detector` 或 `hsv_*` 参数。
- headless camera runtime 不再接受 HSV 分支，始终加载 `YoloBallDetector`。
- 文档中的 `--detector hsv` 示例和 HSV fallback 说明已删除。
- YOLO 标注网页中的 motion/HSV 自动标注辅助未改动；它不属于本次 runtime stereo/headless 范围。

## 验证结果

```bash
rg -n "\bHSV\b|\bhsv\b|HsvBallDetector|--detector|hsv_|args\.detector|detector_name" scripts tools/stereo src/tennisbot_headless_vision docs/current -g '!runtime_hsv_removal_20260703.md' -g '!**/node_modules/**' -g '!**/__pycache__/**'
cd tools/stereo && uv run pytest -q
bun scripts/stereo.ts --help
bun scripts/stereo.ts gui --help
bun scripts/stereo.ts gui --dry-run
PYTHONPATH=src/tennisbot_headless_vision uv run --project tools/stereo python -m unittest discover -s src/tennisbot_headless_vision/tests -v
```

- Runtime HSV residual search returned no matches.
- `tools/stereo` tests passed: `5 passed`.
- `scripts/stereo.ts` usage and GUI help no longer show `--detector` or `--hsv-*` options.
- `scripts/stereo.ts gui --dry-run` prints `detector=yolo`.
- Headless trajectory tests passed: `Ran 4 tests`.
