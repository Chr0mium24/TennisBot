# AGENTS.md

## Project Rules

- 每次改动都要 commit，并在完成前整理好工作区。
- Python 项目使用 `uv`。
- 前端项目使用 TypeScript 和 `bun`。
- 制定计划和实验结果要保存为 Markdown 文档。

## Board Device / Connection Notes

- 当前已知板端设备（2026-06-17 复核）：
  - USB ADB 序列号：`5a8e54bcb540b5ba`
  - ADB 状态：`device`
  - 板端 `wlan0` 地址：`192.168.10.1/24`
  - WiFi 标记：`DD54`
- 连接前先确认实际状态，设备信息可能随现场环境变化：
  - `adb devices -l`
  - `adb shell "ip -o -4 addr show scope global"`
  - `adb shell "cat /oem/wifi_ssid_marker.txt 2>/dev/null | tail -c 5; echo"`
- 长期开发、部署、看日志优先使用 SSH：`ssh <user>@<board-ip>`。
- 设备控制、摄像头切换和救援调试保留 USB ADB：
  - `adb shell "echo uvc_cam1 > /tmp/feat_sw/pipe"`
  - `adb shell "echo uvc_cam2 > /tmp/feat_sw/pipe"`
- 无线 ADB 只用于临时调试，且只在用户明确需要时开启：
  - `adb tcpip 5555`
  - `adb connect <board-ip>:5555`
  - `adb disconnect <board-ip>:5555`
  - `adb usb`
- 更详细的板端连接文档见 `BoardCameraConsole/docs/board_connection_guide.md`。

## TennisWebSim / ROS Rules

- WebSim 的真实接球闭环必须依赖 ROS/Gazebo 后端位姿与控制链路。
- 禁止为了无 ROS/Gazebo 测试而新增本地小车追踪、预测落点追随、接球替身逻辑，避免掩盖真实后端问题。
- 无 ROS/Gazebo 时可以测试前端渲染、视觉投影、轨迹预测等纯前端能力，但不能宣称完成真实接球闭环验证。
