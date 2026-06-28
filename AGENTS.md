# AGENTS.md

## Project Rules

- 每次改动都要 commit，并在完成前整理好工作区。
- Python 项目使用 `uv`。
- 前端项目使用 TypeScript 和 `bun`。
- 制定计划和实验结果要保存为 Markdown 文档。

## TennisWebSim / ROS Rules

- WebSim 的真实接球闭环必须依赖 ROS/Gazebo 后端位姿与控制链路。
- 禁止为了无 ROS/Gazebo 测试而新增本地小车追踪、预测落点追随、接球替身逻辑，避免掩盖真实后端问题。
- 无 ROS/Gazebo 时可以测试前端渲染、视觉投影、轨迹预测等纯前端能力，但不能宣称完成真实接球闭环验证。
