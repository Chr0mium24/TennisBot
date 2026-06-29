# TennisBot Live3D

`apps/live3d` 是本机实机视觉运行界面。它负责：

- 打开浏览器里的左右 USB 相机视频流
- 加载 YOLO 模型包和双目标定包
- 在左右画面上显示 YOLO 检测框
- 调用 `packages/core` 做左右匹配、三角化和轨迹预测
- 渲染 3D 点、轨迹、预测曲线和落点
- 暴露 `window.__tennisbotLive3dSnapshot` 给硬件验证脚本读取

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

## 硬件链路验证

```bash
bun run verify:hardware
```

默认值：

- `--app-url http://localhost:5178`
- `--timeout-ms 30000`
- `--poll-ms 500`
- `--chrome-debug-port 9233`
- `--output ../../docs/archive/YYYYMMDD/live3d/live3d_hardware_loop_<timestamp>.md`
- `--capture-dir <output>_frames`
- `--uvc-devices /dev/video0,/dev/video2`

拉高本地 USB 摄像头曝光/增益：

```bash
bun run verify:hardware -- --prepare-uvc-controls
```

指定设备：

```bash
bun run verify:hardware -- --prepare-uvc-controls --uvc-devices /dev/video0,/dev/video2
```

通过标准：运行时快照必须达到 `prediction-ready`。如果画面可读但没有可见网球，
报告会把左右 YOLO 检测标记为 `blocked`，不会把它当成真实硬件验收通过。

## 默认 artifact 路径

Live3D 默认读取：

```text
/artifacts/models/tennis_ball_yolo
/artifacts/calibration/stereo_cam1_cam2
```

这些是运行时 artifact 包路径，不是训练数据集或标定采集目录。
