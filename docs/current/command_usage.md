# 命令入口使用说明

日期：2026-07-03

## 约定

Python 工具使用 `uv`，前端和 TypeScript 脚本使用 `bun`。入口命令都提供默认
路径、默认设备或默认端口；直接运行默认命令应该能进入最常用流程。

`tools/calibration` 和 `tools/yolo` 的标注/模型包命令都可以在无
`torch`、无 CUDA/NVIDIA Python 包的环境里运行。不要使用
`uv sync --all-extras` 或 `uv run --extra detect ...`，除非要跑纯 YOLO
相机检测 GUI。

## 本机运行入口

本仓库只构建视觉运行时包。`target_msgs` 和 `target_manager` 来自
`/home/cr/tennis_robot_ws/install/setup.bash` 对应的控制工作区：

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
source install/setup.bash
```

默认值：

- `tennisbot_vision_runtime` 订阅 `/robot/chassis_position`
- `tennisbot_vision_runtime` 直接发布 `/target/raw`
- 外部 `target_manager` 订阅 `/target/raw` 并发布 `/target/managed`
- 名义频率：vision raw target 最高 30 Hz，managed target 最高 10 Hz

启动视觉运行时主链路：

```bash
ros2 launch tennisbot_vision_runtime vision_runtime.launch.py
```

启动外部 target manager：

```bash
ros2 launch target_manager target_manager.launch.py
```

也可以用 Bun 主链路入口同时启动视觉运行时和外部 target manager。运行阶段
Bun 默认会在子进程里自动 source ROS、控制工作区和本仓库
`install/setup.bash`，所以启动主链路时不需要在当前终端手动 source：

```bash
bun scripts/vision-runtime.ts run
bun scripts/vision-runtime.ts run --record --session test01 --tile
bun scripts/vision-runtime.ts task --task-id 42 --session catch42 --tile
bun scripts/vision-runtime.ts run --dry-run --record --devices /dev/video0,/dev/video2
```

如果要手动执行 `ros2 topic list`、`ros2 node list` 这类诊断命令，当前终端
仍然需要按上面的顺序 source；Bun 的自动 source 只作用于它启动的子进程。

`run --record` 和 `task` 会默认写入 `runs/vision-runtime/<session>/`：

- `session.json`
- `left.mp4`、`right.mp4`
- `frames.ndjson`
- `chassis.ndjson`
- `detections.ndjson`
- `observations.ndjson`
- `targets.ndjson`
- `events.ndjson`

查看接口和话题：

```bash
ros2 interface show target_msgs/msg/ChassisPosition
ros2 interface show target_msgs/msg/RawTarget
ros2 interface show target_msgs/msg/ManagedTarget
ros2 topic list -t
ros2 topic hz /robot/chassis_position
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

启动本机 4K 双目 YOLO 坐标 GUI：

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui
```

常用选项：

```bash
bun scripts/stereo.ts record --duration 60
bun scripts/stereo.ts record --dry-run
bun scripts/stereo.ts preview
bun scripts/stereo.ts gui --tile
bun scripts/stereo.ts gui --tile --record-run
bun scripts/stereo.ts gui --dry-run
bun scripts/stereo.ts gui --devices /dev/video0,/dev/video2
bun scripts/stereo.ts replay
```

默认值：

- 相机：`/dev/video0,/dev/video2`
- 分辨率：`3840x2160`
- 帧率：`30`
- 格式：`MJPG`
- 标定包：`artifacts/calibration/stereo_cam1_cam2`
- 模型：`artifacts/models/tennis_ball_yolo/model.pt`
- 原始双目视频目录：`runs/raw-stereo`
- GUI 点流记录目录：`runs/stereo`

`record` 写入 `left.mp4`、`right.mp4`、`session.json`、`frames.ndjson` 和
`pairs.ndjson`。不传 `--duration` 时会一直录制，预览窗口按 `q` 或 `esc`
停止；预览只做原始双目画面降采样，不运行 YOLO、矫正或 overlay。

`replay` 会打开本地前端，列出 `runs/stereo` 下面的记录；选中记录后在
页面里用两个进度条选择轨迹时间段，并基于选中点系生成 3D 显示和相机坐标
预测曲线。时间段不通过命令行参数传入。

## YOLO 标注、抠球审核和增强

详细流程见 [YOLO 标注、抠球审核和数据增强使用说明](yolo_sprite_augmentation_usage.md)。

常用入口：

```bash
bun scripts/yolo.ts annotate
bun scripts/yolo.ts sprites extract
bun scripts/yolo.ts sprites review
bun scripts/yolo.ts augment copy-paste
```

对当前 `tools/yolo/0260701` 数据目录进行局域网标注：

```bash
bun scripts/yolo.ts annotate \
  --images-root tools/yolo/0260701/images \
  --labels-root tools/yolo/0260701/labels \
  --excluded-file tools/yolo/0260701/excluded_images.txt \
  --host 0.0.0.0 \
  --port 8765
```

生成 sprite 候选时默认不覆盖已有候选；只有显式加 `--overwrite` 才会重写。

## 标定快捷入口

从仓库根目录运行：

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts preview
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

默认值：

- 亮度检查设备：`/dev/video0,/dev/video2`
- 预览调试设备：`/dev/video0,/dev/video2`
- `cam1` 设备：`/dev/video0`，输出：`artifacts/calibration/cam1_<local_timestamp>`
- `cam2` 设备：`/dev/video2`，输出：`artifacts/calibration/cam2_<local_timestamp>`
- 双目标定设备：左 `/dev/video0`，右 `/dev/video2`
- 双目输入：默认使用最新 accepted 的 `cam1*` / `cam2*` 单目标定包
- 双目输出：`artifacts/calibration/stereo_cam1_cam2_<local_timestamp>`
- 配置：`tools/calibration/configs/dfoptix_charuco_15mm_capture.yaml`
- 采集张数：`30`

常用选项：

```bash
bun scripts/calib.ts preview cam1
bun scripts/calib.ts preview cam2 --shutter 400 --gain 64
bun scripts/calib.ts mono cam1 --capture-only
bun scripts/calib.ts mono cam1 --solve-only --session tools/calibration/captures/local/<session>
bun scripts/calib.ts stereo --dry-run
bun scripts/calib.ts stereo --devices /dev/video0,/dev/video2
bun scripts/calib.ts stereo --output artifacts/calibration/stereo_cam1_cam2
```

正常标定顺序是先检查亮度和相机顺序，再分别完成 `cam1`、`cam2` 单目，
最后完成双目。`mono` 和 `stereo` 默认都是“采集 GUI 结束后继续求解并导出
新的时间戳标定包”。如需让一次求解写入运行时默认读取的固定包，需显式指定
`--output artifacts/calibration/stereo_cam1_cam2`。`preview` 会打开 OpenCV 实时画面，
窗口滑条可调 `shutter/exposure_time_absolute` 和 `gain`，`q` 或 `esc` 退出。
`mono/stereo --dry-run` 只打印底层命令；`brightness/preview --dry-run`
不采集图像帧。

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

## 相机视频调试

双目预览并调快门/增益/亮度：

```bash
bun scripts/calib.ts preview
```

单路预览：

```bash
bun scripts/calib.ts preview cam1
bun scripts/calib.ts preview cam2
```

指定初始参数：

```bash
bun scripts/calib.ts preview cam2 --shutter 400 --gain 64 --brightness 32
```

默认值：

- 双目设备：`/dev/video0,/dev/video2`
- `cam1` 设备：`/dev/video0`
- `cam2` 设备：`/dev/video2`
- 分辨率：`3840x2160`
- 帧率：`30`
- 输入格式：`MJPG`
- 默认切到手动曝光，并将 `shutter`、`gain`、`brightness` 初始化到高可见值，方便先看到画面再下调

窗口操作：

- 滑条：`shutter` 调 `exposure_time_absolute`
- 滑条：`gain` 调 UVC `gain`
- 滑条：`brightness` 调 UVC `brightness`
- 退出：`q` 或 `esc`

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

从仓库根目录启动标注前端：

```bash
bun scripts/yolo.ts annotate
```

也可以直接进入工具目录运行：

```bash
cd tools/yolo
uv run tennisbot-yolo annotate
```

默认 `uv sync` 不安装 `torch`、`ultralytics` 或 CUDA/NVIDIA Python 包。
`detect-gui` 是 `tools/yolo` 中唯一需要 `--extra detect` 的命令。

默认值：

- 图片目录：`tools/yolo/workspace/dataset/images`
- 标签目录：`tools/yolo/workspace/dataset/labels`
- 排除列表：`tools/yolo/workspace/dataset/excluded_images.txt`
- 地址：`127.0.0.1:8765`

指定端口：

```bash
bun scripts/yolo.ts annotate --port 8766
```

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

注意：`tools/yolo detect-gui` 只显示检测框；需要显示球相对相机的
x/y/z 坐标时使用根入口 `bun scripts/stereo.ts gui`。

离线导出已有视频的 YOLO 带框结果：

```bash
bun scripts/yolo.ts detect-video input.mp4 \
  --output runs/yolo-detect/input_boxes.mp4 \
  --tile \
  --overwrite
```

等价的工具目录命令：

```bash
cd tools/yolo
uv run --extra detect tennisbot-yolo detect-video ../../input.mp4 \
  --output ../../runs/yolo-detect/input_boxes.mp4 \
  --tile \
  --overwrite
```

默认会保留原视频分辨率和 FPS，输出 mp4v 编码的视频，只包含检测框、中心点、
置信度和状态 overlay，不保留音频。这个命令只验证 2D YOLO 检测效果，不验证
双目几何、轨迹预测、ROS 发布或真实接球闭环。
