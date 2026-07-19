# 命令入口使用说明

日期：2026-07-19

所有 Python 入口从仓库根目录用 `uv run` 执行。

## Camera

```bash
uv run scripts/camera.py list
uv run scripts/camera.py check
uv run scripts/camera.py preview cam1
uv run scripts/camera.py preview cam2
uv run scripts/camera.py preview stereo
uv run scripts/camera.py controls show stereo
uv run scripts/camera.py controls apply stereo --profile runtime
uv run scripts/camera.py controls apply stereo --profile calibration
```

`cam1` 是 left `/dev/video0`，`cam2` 是 right `/dev/video2`。`preview` 只显示
原始画面，不运行 YOLO、不标定、不录制。

## Calibration

```bash
uv run scripts/calib.py online mono cam1
uv run scripts/calib.py online mono cam2
uv run scripts/calib.py online stereo

uv run scripts/calib.py offline mono cam1 --session <path>
uv run scripts/calib.py offline mono cam2 --session <path>
uv run scripts/calib.py offline stereo --session <path>
```

online 一定打开 ChArUco GUI，完成采集后继续求解；offline 一定不打开相机或
GUI，只求解明确指定的 session。可用 `--output` 指定标定包位置，用
`--dry-run` 检查底层步骤。

## Recording

```bash
uv run scripts/record.py mono cam1
uv run scripts/record.py mono cam2 --duration 60
uv run scripts/record.py stereo
uv run scripts/record.py mono cam1 --gui
uv run scripts/record.py stereo --gui
```

默认 headless，适合 SSH。mono/stereo 和 GUI/headless 使用相同 ffmpeg 录制、
控制 profile 和 session schema。输出位于 `runs/recording`，包含
`session.json`、视频、`frames.ndjson`，双目另含 `pairs.ndjson`。

## Test

```bash
uv run scripts/test.py yolo mono cam1
uv run scripts/test.py yolo mono cam2 --gui
uv run scripts/test.py yolo stereo
uv run scripts/test.py yolo stereo --gui
uv run scripts/test.py triangulation stereo
uv run scripts/test.py triangulation stereo --gui
uv run scripts/test.py communication chassis-position
```

headless 持续输出检测数、置信度、FPS、推理延迟和 pair delta；三角化另输出
相机坐标 `x/y/z`、disparity、epipolar 和 reprojection error。加 `--json`
输出 NDJSON 风格的一行一帧诊断。

只有在线 test 支持录制：

```bash
uv run scripts/test.py yolo mono cam1 --record
uv run scripts/test.py yolo stereo --gui --record
uv run scripts/test.py triangulation stereo --record
uv run scripts/test.py triangulation stereo --gui --record-overlay
```

`--record-overlay` 自动启用 `--record`。可用 `--record-root` 和
`--record-session` 指定会话。录制 sink 使用测试进程已经打开的 frame，不会
二次打开相机。

## ROS runtime

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
uv pip install -e packages/vision-python
colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
source install/setup.bash
uv run scripts/vision-runtime.py run
```

通信测试只读真实 ROS topic，不生成球、目标或本地底盘替身。
