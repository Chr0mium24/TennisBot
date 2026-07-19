# TennisBot 当前架构

日期：2026-07-19

## 操作入口

相机相关业务统一为四个根入口：

```text
scripts/camera.py  -> list / check / preview / controls
scripts/calib.py   -> online|offline × mono|stereo
scripts/record.py  -> mono|stereo × headless|GUI
scripts/test.py    -> YOLO / triangulation / communication diagnostics
```

`scripts/vision-runtime.py` 仍负责真实 ROS 视觉运行时。YOLO 数据、标注和模型包
由 `scripts/yolo.py` 负责，不属于在线相机诊断入口。

## Python 能力边界

`packages/vision-python` 是共享的 `tennisbot-vision` uv 包：

- `tennisbot_camera`：稳定 `cam1`/`cam2` 身份、左右顺序、采集配置、控制
  profile、mono/stereo frame source、时间戳和 raw preview；
- `tennisbot_vision`：运行时标定包加载、YOLO、ROI、双目匹配、矫正、三角化、
  GUI/终端诊断和可附着的测试录制 sink。

`tools/calibration` 保留 ChArUco GUI 采集、质量门槛和 mono/stereo 求解器。
`tools/recording` 保留 ffmpeg/V4L2 编码、会话、时间戳导出和 GUI。二者是独立
uv 项目，但都消费共享相机配置。

`src/tennisbot_vision_runtime` 直接依赖安装后的 `tennisbot-vision`，不再把
工具源目录插入 `sys.path`。运行时使用相同的标定加载、检测与匹配算法。

## 数据流

```text
canonical camera config
  -> mono/stereo frame source
  -> YOLO
  -> optional stereo matching + triangulation
  -> GUI or structured terminal output
  -> optional test recording sink (same already-open frames)
```

独立 `record` 使用 ffmpeg 直接保存相机 MJPEG。`test --record` 不能启动第二个
录制进程重新打开 V4L2，而是把测试循环已经取得的 frame 交给 in-process sink。

ROS 真实闭环仍为：

```text
stereo cameras + /robot/chassis_position
  -> tennisbot_vision_runtime
  -> /target/raw
  -> external target_manager
  -> /target/managed
```

没有 ROS/Gazebo 后端时只能验证纯视觉和前端能力，不能声称完成真实接球闭环。
视觉数据必须尽早转换到球场/接口坐标系，再做轨迹拟合和目标发布。

## 配置与产物

- 相机身份和 profile：`packages/vision-python/src/tennisbot_camera/camera_config.yaml`
- 标定采集配置：`tools/calibration/configs/dfoptix_charuco_15mm_capture.yaml`
- 录制编码配置：`tools/recording/configs/tennis_camera_recording.yaml`
- 标定包：`artifacts/calibration/`
- 模型包：`artifacts/models/`
- 录制：`runs/recording/`
- 在线测试录制：`runs/test/`
- ROS runtime 日志：`runs/vision-runtime/`

旧 `scripts/stereo.py`、`scripts/recording.py`、`tools/stereo` 和 replay 已移除。
