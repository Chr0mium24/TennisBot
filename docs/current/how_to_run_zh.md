# TennisBot 中文运行说明

日期：2026-07-03

## 先分清两个工作区

主链路现在不是一个仓库全部包起来跑。运行时分成两个工作区：

```text
/home/cr/tennis_robot_ws
  target_msgs
  target_manager
  底盘 / 仿真 / 控制相关 ROS 包

/home/cr/Codes/TennisBot
  src/tennisbot_vision_runtime
  scripts/vision-runtime.ts
  tools/calibration
  tools/stereo
  tools/yolo
  artifacts/calibration/stereo_cam1_cam2
  artifacts/models/tennis_ball_yolo
```

`target_manager` 不在 TennisBot 仓库里构建。TennisBot 只构建并运行
`tennisbot_vision_runtime`，它发布 `/target/raw`；外部 `target_manager`
订阅 `/target/raw`，再发布 `/target/managed` 给规划/状态机。

主链路数据流：

```text
/robot/chassis_state
  -> chassis_position_publisher
  -> /robot/chassis_position
  -> tennisbot_vision_runtime

双目相机
  -> tennisbot_vision_runtime
  -> /target/raw
  -> target_manager
  -> /target/managed
  -> 底盘规划 / 状态机
```

## 新电脑部署顺序

### 1. 准备基础工具

需要先装好这些工具：

- ROS 2 Humble
- `colcon`
- `bun`
- `uv`
- 摄像头和 YOLO 所需的系统图形/视频依赖

如果目标机器只做无相机 dry-run，可以先不处理摄像头权限；真实双目运行时要能
访问 `/dev/video0` 和 `/dev/video2`，或者运行时显式传入设备。

### 2. 准备控制工作区

先准备 `/home/cr/tennis_robot_ws`，并确认它能提供 `target_msgs` 和
`target_manager`：

```bash
cd /home/cr/tennis_robot_ws
source /opt/ros/humble/setup.bash
colcon build --symlink-install
source install/setup.bash

ros2 pkg list | grep -E 'target_msgs|target_manager'
ros2 interface show target_msgs/msg/ChassisPosition
ros2 interface show target_msgs/msg/RawTarget
ros2 interface show target_msgs/msg/ManagedTarget
```

如果这里失败，先修控制工作区。TennisBot 这边依赖这两个 ROS 包。

### 3. 准备 TennisBot 仓库

```bash
cd /home/cr/Codes/TennisBot
git pull
```

确认默认标定包和模型包存在。它们已经是 Git 跟踪文件，新电脑 clone/pull 后
应该直接有：

```bash
test -d artifacts/calibration/stereo_cam1_cam2 && echo calibration_ok
test -f artifacts/models/tennis_ball_yolo/model.pt && echo model_ok
```

只有在换相机安装位置、换双目设备或换模型时，才需要重新生成这些 artifact。

### 4. 构建 TennisBot 里的 ROS 包

构建阶段仍然要按顺序 source，因为 `colcon build` 需要先知道 ROS 和外部
`target_msgs` 在哪里：

```bash
cd /home/cr/Codes/TennisBot
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash

colcon build --base-paths src --packages-select tennisbot_vision_runtime --symlink-install
source install/setup.bash
```

注意这里不要 build `target_manager`，也不要加
`--allow-overriding target_manager`。`target_manager` 属于
`/home/cr/tennis_robot_ws`。

## 每次开机后的最短运行命令

### 1. 直接用 Bun 启动

```bash
cd /home/cr/Codes/TennisBot
bun scripts/vision-runtime.ts run --record --session test01 --tile
```

Bun 入口默认会在它启动的 ROS 子进程里自动执行：

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
source /home/cr/Codes/TennisBot/install/setup.bash
```

所以运行主链路时，当前终端可以不手动 source。这个自动 source 只作用于 Bun
启动的子进程，不会把你的当前终端变成 ROS 环境。

默认 setup 路径可以用环境变量覆盖：

```bash
ROS_SETUP=/opt/ros/humble/setup.bash \
TENNISBOT_CONTROL_SETUP=/home/cr/tennis_robot_ws/install/setup.bash \
TENNISBOT_LOCAL_SETUP=/home/cr/Codes/TennisBot/install/setup.bash \
bun scripts/vision-runtime.ts run --record --session test01 --tile
```

也可以在命令行上控制：

```bash
bun scripts/vision-runtime.ts run --no-auto-source
bun scripts/vision-runtime.ts run --clear-setup-files \
  --setup-file /opt/ros/humble/setup.bash \
  --setup-file /home/cr/tennis_robot_ws/install/setup.bash \
  --setup-file /home/cr/Codes/TennisBot/install/setup.bash
```

### 2. 手动查看 ROS 状态前先 source 当前终端

如果你要自己敲 `ros2 pkg list`、`ros2 topic list`、`ros2 node list`，当前
终端仍然要 source：

```bash
cd /home/cr/Codes/TennisBot
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
source install/setup.bash
```

然后确认 ROS 包和话题接口：

```bash
ros2 pkg list | grep -E 'target_msgs|target_manager|tennisbot_vision_runtime'
ros2 interface show target_msgs/msg/ChassisPosition
ros2 interface show target_msgs/msg/RawTarget
ros2 interface show target_msgs/msg/ManagedTarget
```

### 3. 确认底盘位置输入

真实主链路需要 interface 层发布 `/robot/chassis_position`，消息类型是
`target_msgs/ChassisPosition`。其中 `x/y/yaw` 必须已经是球场/接口坐标系：

```text
publish_stamp
sequence_id
x
y
yaw
```

`/robot/chassis_state` 仍然可以作为底盘或仿真的原始数组输入，但它应该先进入
外部 `chassis_position_publisher_node`，再由该节点发布
`/robot/chassis_position` 给视觉节点。

检查：

```bash
ros2 topic list -t
ros2 topic hz /robot/chassis_position
ros2 topic echo /robot/chassis_position
```

如果没有 `/robot/chassis_position`，视觉节点会等待，不应该把无底盘输入的
本地替身逻辑当成真实接球闭环。

### 4. dry-run 看 Bun 会启动什么

```bash
bun scripts/vision-runtime.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
```

正常会打印两条命令：

```text
bash -lc 'source /opt/ros/humble/setup.bash && source /home/cr/tennis_robot_ws/install/setup.bash && source /home/cr/Codes/TennisBot/install/setup.bash && exec ros2 launch target_manager target_manager.launch.py'
bash -lc 'source /opt/ros/humble/setup.bash && source /home/cr/tennis_robot_ws/install/setup.bash && source /home/cr/Codes/TennisBot/install/setup.bash && exec ros2 run tennisbot_vision_runtime vision_runtime_node --ros-args ...'
```

第一条来自外部控制工作区，第二条来自 TennisBot。

### 5. 真实启动主链路

默认会同时启动外部 `target_manager` 和本仓库的视觉运行时节点。这里不需要
再手动 source：

```bash
bun scripts/vision-runtime.ts run --record --session test01 --tile
```

常用变体：

```bash
# 不分块 YOLO，使用配置默认值
bun scripts/vision-runtime.ts run --record --session test01

# 指定双目设备
bun scripts/vision-runtime.ts run --record --session test01 --devices /dev/video0,/dev/video2

# target_manager 已经在别的终端启动时，只启动视觉节点
bun scripts/vision-runtime.ts run --record --session test01 --no-manager
```

## 单次 task 触发

单次任务用 `task` 子命令。它会把 `task_id` 传给视觉运行时节点，默认打开日志，
并在任务完成后让视觉运行时节点退出：

```bash
bun scripts/vision-runtime.ts task --task-id 42 --session catch42 --tile
```

如果只想记录文本数据，不录双路视频：

```bash
bun scripts/vision-runtime.ts task --task-id 42 --session catch42 --no-video
```

## 日志和录像在哪里

`run --record` 和 `task` 默认写到：

```text
runs/vision-runtime/<session>/
```

主要文件：

```text
session.json       会话参数和启动信息
left.mp4           左目视频
right.mp4          右目视频
frames.ndjson      帧时间戳
chassis.ndjson     底盘输入和转换后的 field pose
detections.ndjson  YOLO 检测和双目匹配诊断
observations.ndjson 选中的球点观测
targets.ndjson     发布到 /target/raw 的目标
events.ndjson      运行事件和错误
```

这些文件用于复盘：能同时对齐双路视频、底盘位置、YOLO 结果、双目三角化结果
和最终 `/target/raw`。

## 手动分开启动

不用 Bun 也可以分两个终端手动跑。

终端 A：

```bash
cd /home/cr/Codes/TennisBot
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
source install/setup.bash

ros2 launch target_manager target_manager.launch.py
```

终端 B：

```bash
cd /home/cr/Codes/TennisBot
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
source install/setup.bash

ros2 launch tennisbot_vision_runtime vision_runtime.launch.py
```

Bun 入口只是把这两个进程按统一参数启动，并把日志参数、task 参数、设备参数
转换成 ROS 参数传给视觉运行时节点。

## 相机和标定检查

先看设备亮度和画面：

```bash
bun scripts/calib.ts brightness
bun scripts/calib.ts preview
```

重新标定顺序：

```bash
bun scripts/calib.ts mono cam1
bun scripts/calib.ts mono cam2
bun scripts/calib.ts stereo
```

默认输出：

```text
artifacts/calibration/cam1
artifacts/calibration/cam2
artifacts/calibration/stereo_cam1_cam2
```

如果只想看本机双目 YOLO 坐标 GUI，不接 ROS：

```bash
bun scripts/stereo.ts record
bun scripts/stereo.ts gui --tile
```

这只是本机诊断工具，不能算真实接球闭环验证。

## 常见问题

### 找不到 `target_msgs` 或 `target_manager`

如果是手动执行 `ros2 ...` 命令时报错，原因通常是当前终端没有 source 控制
工作区：

```bash
source /opt/ros/humble/setup.bash
source /home/cr/tennis_robot_ws/install/setup.bash
```

再检查：

```bash
ros2 pkg list | grep -E 'target_msgs|target_manager'
```

如果是通过 `bun scripts/vision-runtime.ts run` 启动时报错，先确认 Bun 自动 source
用到的 setup 文件存在：

```bash
test -f /opt/ros/humble/setup.bash
test -f /home/cr/tennis_robot_ws/install/setup.bash
test -f /home/cr/Codes/TennisBot/install/setup.bash
```

新电脑路径不同的话，用 `TENNISBOT_CONTROL_SETUP` 和
`TENNISBOT_LOCAL_SETUP` 覆盖默认路径。

### `colcon build` 找不到 `target_msgs`

构建 TennisBot 前必须先 build 并 source `/home/cr/tennis_robot_ws`。TennisBot
不再包含本地 `target_msgs` 或 `target_manager` 副本。

### 没有 `/target/raw`

先查四件事：

```bash
ros2 topic hz /robot/chassis_position
ls artifacts/calibration/stereo_cam1_cam2
ls artifacts/models/tennis_ball_yolo/model.pt
bun scripts/vision-runtime.ts run --dry-run --record --devices /dev/video0,/dev/video2
```

视觉节点只有在有近期底盘位置、双目相机帧、YOLO 检测和有效双目匹配时才发布
`/target/raw`。

### 有 `/target/raw` 但没有 `/target/managed`

确认外部 `target_manager` 正在运行：

```bash
ros2 node list
ros2 topic echo /target/raw
ros2 topic echo /target/managed
```

如果 Bun 是用 `--no-manager` 启动的，需要在别的终端手动启动
`target_manager`。

### Python 依赖缺失

真实相机 YOLO 运行需要 ROS 进程能 import `numpy`、`cv2` 和 `ultralytics`。
本仓库的 Python 工具使用 `uv` 管理；部署镜像里也要保证 ROS 运行环境能访问
这些依赖。无相机链路排查时可以先用 dry-run 或关闭相机参数确认 ROS topic
链路。

## 推荐验收命令

```bash
uv run -- python -m compileall -q src/tennisbot_vision_runtime
PYTHONPATH=src/tennisbot_vision_runtime uv run python -m unittest discover -s src/tennisbot_vision_runtime/tests -v
bun scripts/vision-runtime.ts --help
bun scripts/vision-runtime.ts run --dry-run --record --devices /dev/video0,/dev/video2 --session dryrun
```

真实验收还需要真实底盘链路提供 `/robot/chassis_position`，并确认
`/target/raw` 和 `/target/managed` 的时间、坐标和频率都正确。
