# TennisBot Live3D

`apps/live3d` 是本机实机视觉运行界面。它负责：

- 打开浏览器里的左右 USB 相机视频流
- 加载 YOLO 模型包和双目标定包
- 在左右画面上显示 YOLO 检测框
- 调用 `packages/core` 做左右匹配、三角化和轨迹预测
- 渲染 3D 点、轨迹、预测曲线和落点
- 暴露 `window.__tennisbotLive3dSnapshot` 便于本地调试和自动化检查

注意：当前 3D 输出是相机坐标系下的几何结果，不是网球场世界坐标。要声明球场
坐标，需要再测量并加载相机外参到球场的变换。

## 安装

```bash
cd apps/live3d
bun install
```

## 开发运行

```bash
bun run dev
```

默认值：

- 地址：`http://127.0.0.1:5178/`
- 构建：先执行 `bun run build`
- 静态服务：`scripts/serve.js`

## 验证

```bash
bun test
bun run typecheck
bun run build
```

## 默认 artifact 路径

Live3D 默认读取：

```text
/artifacts/models/tennis_ball_yolo
/artifacts/calibration/stereo_cam1_cam2
```

这些是运行时 artifact 包路径，不是训练数据集或标定采集目录。
