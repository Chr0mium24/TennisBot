# YOLO Sprite Review Five-Point Mask Editing

日期：2026-07-03

## 目标

把 `tools/yolo/web/yolo-sprite-review` 的椭圆 mask 编辑从右侧参数输入改成
画布上的五点椭圆交互，参考 `jlc_labeler` 的五点拟合实现。

## 计划

1. 阅读 `jlc_labeler/labeler/data.js` 的五点椭圆拟合算法。
2. 阅读 `jlc_labeler/labeler/editor.js` 和 `canvas.js` 的拟合点拖动与绘制方式。
3. 移除 sprite review 页面的中心、半径和旋转参数控件。
4. 从现有 mask 生成五个边界点，在 canvas 中拖动点后重新拟合椭圆。
5. 保持现有 `/api/sprites/{id}/mask` payload，不修改 Python 后端存储契约。

## 结果

- `index.html` 已改成两栏布局，右侧参数面板已移除。
- Reload 移到顶部工具栏。
- 每个候选加载时会从当前 mask 生成五个边界控制点。
- 拖动控制点会通过五点拟合更新椭圆 mask。
- 拖动椭圆内部会整体平移五个控制点。
- Save、Approve、Reject 仍使用原有 mask JSON。

## 验证结果

```bash
perl -0ne 'print $1 if /<script>([\s\S]*)<\/script>/' tools/yolo/web/yolo-sprite-review/index.html | node --check -
uv run pytest -q
uv run --project tools/yolo --extra augment tennisbot-yolo sprites review --help
curl -fsS http://127.0.0.1:8766/api/health
curl -fsS http://127.0.0.1:8766/api/sprites
```

- JS 语法检查通过。
- `tools/yolo` 测试结果：`19 passed in 1.37s`。
- `sprites review --help` 正常。
- 本地 review 服务 smoke 通过，`/api/sprites` 返回 4 个候选。
- 页面 HTML 中不再包含 Center/Radius/Feather 参数控件。
