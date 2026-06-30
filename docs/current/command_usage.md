# 命令入口使用说明

日期：2026-06-30

## 约定

Python 工具使用 `uv`，前端和 TypeScript 脚本使用 `bun`。入口命令都提供默认
路径、默认设备或默认端口；直接运行默认命令应该能进入最常用流程。

## 本机运行入口

启动 Live3D：

```bash
bun scripts/live3d.ts
```

默认值：

- Live3D URL：`http://127.0.0.1:5178/`
- 日志：`/tmp/tennisbot_live3d.log`
- 行为：构建并启动缺失服务

只检查服务状态：

```bash
bun scripts/live3d.ts --status
```

## 标定快捷入口

从仓库根目录运行：

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

默认值：

- 亮度检查设备：`/dev/video0,/dev/video2`
- `cam1` 设备：`/dev/video0`，输出：`artifacts/calibration/cam1`
- `cam2` 设备：`/dev/video2`，输出：`artifacts/calibration/cam2`
- 双目标定设备：左 `/dev/video0`，右 `/dev/video2`
- 双目输出：`artifacts/calibration/stereo_cam1_cam2`
- 配置：`tools/calibration/configs/dfoptix_charuco_15mm_capture.yaml`
- 采集张数：`30`

常用选项：

```bash
bun scripts/calib.ts mono cam1 --capture-only
bun scripts/calib.ts mono cam1 --solve-only --session tools/calibration/captures/local/<session>
bun scripts/calib.ts stereo --dry-run
bun scripts/calib.ts stereo --devices /dev/video0,/dev/video2
```

正常标定顺序是先检查亮度和相机顺序，再分别完成 `cam1`、`cam2` 单目，
最后完成双目。`mono` 和 `stereo` 默认都是“采集 GUI 结束后继续求解并导出
运行时包”。`mono/stereo --dry-run` 只打印底层命令；`brightness --dry-run`
只枚举设备，不调用 `ffmpeg` 采集图像帧。

## 相机亮度检查

```bash
bun scripts/calib.ts brightness
```

默认值：

- 设备：`/dev/video0,/dev/video2`
- 分辨率：`1280x720`
- 帧率：`30`
- 输入格式：`mjpeg`
- 超时：`5000 ms`

指定设备：

```bash
bun scripts/calib.ts brightness --devices /dev/video0,/dev/video2
```

## 底层标定工具

通常直接使用上面的 `bun scripts/calib.ts ...` 快捷入口。需要排查底层 CLI
时再进入目录：

```bash
cd tools/calibration
```

单目采集 GUI：

```bash
uv run camera-calib-lab capture charuco-auto-gui
```

默认值：

- 配置：`configs/dfoptix_charuco_15mm_capture.yaml`
- 输出：`captures/local/dfoptix_charuco_auto_session`
- 采集张数：`30`
- 相机：`/dev/video0`

双目采集 GUI：

```bash
uv run camera-calib-lab capture stereo-charuco-auto-gui
```

默认值：

- 配置：`configs/dfoptix_charuco_15mm_capture.yaml`
- 输出：`captures/local/dfoptix_stereo_charuco_auto_session`
- 采集组数：`30`
- 左相机：`/dev/video0`
- 右相机：`/dev/video2`

相机 USB 端口变化时：

```bash
uv run camera-calib-lab capture stereo-charuco-auto-gui --left-device /dev/video0 --right-device /dev/video2
```

单目求解并导出运行时包：

```bash
uv run camera-calib-lab solve mono \
  --session captures/local/20260630_cam1_charuco \
  --output ../../artifacts/calibration/cam1 \
  --camera-id cam1

uv run camera-calib-lab solve mono \
  --session captures/local/20260630_cam2_charuco \
  --output ../../artifacts/calibration/cam2 \
  --camera-id cam2
```

双目求解并导出运行时包：

```bash
uv run camera-calib-lab solve stereo \
  --session captures/local/20260630_stereo_charuco \
  --left-mono ../../artifacts/calibration/cam1 \
  --right-mono ../../artifacts/calibration/cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2
```

## YOLO 工具

进入目录：

```bash
cd tools/yolo
```

启动标注前端：

```bash
uv run tennisbot-yolo annotate
```

默认值：

- 图片目录：`tools/yolo/yolo/dataset/images`
- 标签目录：`tools/yolo/yolo/dataset/labels`
- 排除列表：`tools/yolo/yolo/dataset/excluded_images.txt`
- 地址：`127.0.0.1:8765`

验证默认模型包：

```bash
uv run tennisbot-yolo package verify
```

默认值：

- 模型包：`artifacts/models/tennis_ball_yolo`

这个默认模型包已纳入 Git 跟踪，拉取仓库后应直接存在。

创建 dry-run 模型包：

```bash
uv run tennisbot-yolo package create --dry-run
```

默认值：

- 输出：`artifacts/models/tennis_ball_yolo`
- 默认模型类型：`onnx`

创建真实模型包时必须显式传入至少一个模型文件，避免误把空包当成真实模型：

```bash
uv run tennisbot-yolo package create \
  --model-pt ../../artifacts/model_candidates/tennis_ball_yolo/best.pt \
  --default-model pt
```

纯 YOLO 检测 GUI：

```bash
uv run --extra detect tennisbot-yolo detect-gui
```

默认值：

- 相机：`/dev/video0,/dev/video2`
- 分辨率：`3840x2160`
- 帧率：`30`
- 格式：`MJPG`
- 模型：`artifacts/models/tennis_ball_yolo/model.pt`
- 置信度：`0.05`
- 输入尺寸：`1280`
- 预览宽度：`720`

小球太小时建议加 tiled 推理：

```bash
uv run --extra detect tennisbot-yolo detect-gui --tile
```

## Live3D

进入目录：

```bash
cd apps/live3d
```

开发运行：

```bash
bun install
bun run dev
```

验证：

```bash
bun test
bun run typecheck
bun run build
```

硬件链路验证：

```bash
bun run verify:hardware
```

默认值：

- Live3D URL：`http://localhost:5178`
- 超时：`30000 ms`
- 轮询间隔：`500 ms`
- Chrome 调试端口：`9233`
- UVC 设备：`/dev/video0,/dev/video2`
- 报告：`docs/archive/YYYYMMDD/live3d/live3d_hardware_loop_<timestamp>.md`
- 截图目录：`<报告文件名>_frames`

如果需要先拉高本地 USB 摄像头曝光/增益：

```bash
bun run verify:hardware -- --prepare-uvc-controls
```
