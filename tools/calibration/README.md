# TennisBot 标定工具

`tools/calibration` 是当前主线标定采集入口。它只支持本项目使用的固定
DFOptix ChArUco 标定板：

- `DICT_5X5_100`
- 14 x 9 squares
- 15 mm square
- 11.25 mm marker

当前能力包括单目/双目 OpenCV 采集 GUI、ChArUco 求解和运行时标定包导出。

## 安装

```bash
cd tools/calibration
uv sync
```

## 相机亮度检查

```bash
uv run camera-calib-lab camera brightness
```

默认值：

- 自动选择前两个 USB V4L2 采集设备
- `1280x720`
- `30 FPS`
- `mjpeg`
- `5000 ms` 超时

指定设备：

```bash
uv run camera-calib-lab camera brightness --devices /dev/video0,/dev/video2
```

## 相机预览调试

```bash
uv run camera-calib-lab camera preview --device /dev/video0
uv run camera-calib-lab camera preview --devices /dev/video0,/dev/video2
```

默认预览使用 `3840x2160`、`30 FPS`、`MJPG`，并切到手动曝光。启动时会将
`shutter`、`gain`、`brightness` 设到高可见值，窗口滑条可继续下调；`q`
或 `esc` 退出。

指定初始控制值：

```bash
uv run camera-calib-lab camera preview --device /dev/video0 --shutter 400 --gain 64 --brightness 32
```

## 单目采集

```bash
uv run camera-calib-lab capture charuco-auto-gui
```

默认值：

- `--config configs/dfoptix_charuco_15mm_capture.yaml`
- `--output captures/local/dfoptix_charuco_auto_session`
- `--calibration-output ""`
- `--views 30`
- `--device /dev/video0`

指定相机：

```bash
uv run camera-calib-lab capture charuco-auto-gui --device /dev/video2
```

## 双目采集

```bash
uv run camera-calib-lab capture stereo-charuco-auto-gui
```

默认值：

- `--config configs/dfoptix_charuco_15mm_capture.yaml`
- `--output captures/local/dfoptix_stereo_charuco_auto_session`
- `--calibration-output ""`
- `--views 30`
- `--left-device /dev/video0`
- `--right-device /dev/video2`

指定左右相机：

```bash
uv run camera-calib-lab capture stereo-charuco-auto-gui \
  --left-device /dev/video0 \
  --right-device /dev/video2
```

## GUI 按键

- `space`：手动保存当前合格帧
- `c`：结束采集并标记请求标定
- `q` 或 `Esc`：退出

## 输出

工具会写入采集目录，包含：

- `manifest.json`
- `cam1/viewXXX/image.png` 或 `left/right/viewXXX/image.png`
- 每帧 ChArUco 角点数、平均亮度、清晰度

默认采集目录如果已存在，会自动追加时间戳，避免覆盖旧采集。

## 单目求解

对每个相机分别求内参。`--session` 指向上一步单目采集目录，输出目录为单目标定
包：

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

默认验收门槛：

- `--min-views 8`
- `--max-rms-px 1.0`

输出包含：

- `package.json`
- `camera.json`
- `verification.json`
- `calibration_opencv.yaml`
- `summary.md`
- `review.html`

## 双目求解

双目求解需要双目采集目录和左右单目标定包：

```bash
uv run camera-calib-lab solve stereo \
  --session captures/local/20260630_stereo_charuco \
  --left-mono ../../artifacts/calibration/cam1 \
  --right-mono ../../artifacts/calibration/cam2 \
  --output ../../artifacts/calibration/stereo_cam1_cam2 \
  --left-camera-id cam1 \
  --right-camera-id cam2
```

默认验收门槛：

- `--min-pairs 12`
- `--max-rms-px 2.0`
- `--epipolar-warning-px 2.0`
- `--rectification-warning-px 2.0`

输出包含：

- `package.json`
- `cam1.json`
- `cam2.json`
- `stereo.json`
- `rectification.json`
- `verification.json`
- `calibration_opencv.yaml`
- `summary.md`
- `review.html`

`epipolar` 和校正后 `y` 误差超过阈值时会写入质量警告；`stereo RMS`、有效组数
和 baseline 会决定包是否 accepted。
