# TennisBot 标定工具

`tools/calibration` 是当前主线标定采集入口。它只支持本项目使用的固定
DFOptix ChArUco 标定板：

- `DICT_5X5_100`
- 14 x 9 squares
- 15 mm square
- 11.25 mm marker

当前能力重点是单目/双目 OpenCV 采集 GUI 和采集 manifest。新采集数据的完整
mono/stereo solve 与运行时包导出还需要继续主线化。

## 安装

```bash
cd tools/calibration
uv sync
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
