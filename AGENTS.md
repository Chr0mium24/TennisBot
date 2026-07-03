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

## Coordinate Frame Rules

- 球场/接口坐标系以球场几何中心为原点 `(0, 0)`。
- 球场/接口 `x` 轴等于笛卡尔世界系 `+y` 轴。
- 球场/接口 `y` 轴等于笛卡尔世界系 `-x` 轴。
- `z` 轴保持竖直向上，不做轴交换。
- 从笛卡尔世界系到球场/接口坐标系：
  - `field_x = cartesian_y`
  - `field_y = -cartesian_x`
  - `field_z = cartesian_z`
- 从球场/接口坐标系到笛卡尔世界系：
  - `cartesian_x = -field_y`
  - `cartesian_y = field_x`
  - `cartesian_z = field_z`
- 实时视觉算法内部应尽早统一到球场/接口坐标系，再做轨迹拟合、落点/接球平面预测和 ROS interface 发布；禁止只在最终 `/target/raw` 出口临时转换坐标。
- 如果底盘 yaw 来自标准笛卡尔世界系角度，按 `field_yaw = cartesian_yaw - pi / 2` 转成球场/接口 yaw 后再参与视觉算法。
