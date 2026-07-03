# TennisBot 与 tennis_robot_ws 通信测试结果

日期：2026-07-03

## 变更

- `tennisbot_headless_vision` 默认目标平面从地面落点改为接球平面：
  `target_plane_z: 0.6`。
- 删除 TennisBot 仓库内重复的 `src/interface/target_msgs` 包。
- TennisBot 构建说明改为先 source `~/tennis_robot_ws/install/setup.bash`，
  使用控制工作区提供的外部 `target_msgs`。

## 构建

使用命令：

```bash
source /opt/ros/humble/setup.bash
source ~/tennis_robot_ws/install/setup.bash
colcon build --base-paths src --packages-select \
  target_manager tennisbot_vision_msgs \
  tennisbot_interface_adapter tennisbot_headless_vision \
  --symlink-install --allow-overriding target_manager
```

结果：

```text
Summary: 4 packages finished
```

## 通信测试

测试只验证 ROS topic 和消息适配，不启动相机、串口或真实接球闭环。

隔离环境：

```text
ROS_DOMAIN_ID=77
ROS_LOCALHOST_ONLY=1
```

启动节点：

```text
/target_manager
/vision_interface_adapter
```

验证结果：

- 发布 `/robot/chassis_position` 后，收到 `/vision/chassis_position`。
- 发布 `/robot/chassis_state` 后，收到 `/vision/chassis_pose`，包含 yaw。
- 发布 `/vision/target_prediction` 后，收到 `/target/raw`。
