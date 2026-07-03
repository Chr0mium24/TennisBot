#!/usr/bin/env python3
"""Publish chassis x/y position for the vision layer.

Input:
    /robot/chassis_state Float64MultiArray
        [x_m, y_m, v_mps, phi_rad, yaw_rad, ground_speed_mps]

Output:
    /robot/chassis_position target_msgs/ChassisPosition
        publish_stamp, sequence_id, x, y
"""

from __future__ import annotations

import math

import rclpy
from rclpy.node import Node
from std_msgs.msg import Float64MultiArray
from target_msgs.msg import ChassisPosition


def finite_float(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


class ChassisPositionPublisher(Node):
    def __init__(self) -> None:
        super().__init__("chassis_position_publisher")

        self.declare_parameter("state_topic", "/robot/chassis_state")
        self.declare_parameter("position_topic", "/robot/chassis_position")
        self.declare_parameter("publish_rate_hz", 30.0)
        self.declare_parameter("max_state_age_s", 0.20)
        self.declare_parameter("publish_stale_state", False)

        state_topic = str(self.get_parameter("state_topic").value)
        position_topic = str(self.get_parameter("position_topic").value)
        publish_rate_hz = finite_float(
            self.get_parameter("publish_rate_hz").value,
            name="publish_rate_hz",
        )
        if publish_rate_hz <= 0.0:
            raise ValueError("publish_rate_hz must be positive")
        self.max_state_age_s = finite_float(
            self.get_parameter("max_state_age_s").value,
            name="max_state_age_s",
        )
        self.publish_stale_state = bool(self.get_parameter("publish_stale_state").value)

        self.latest_x: float | None = None
        self.latest_y: float | None = None
        self.latest_state_time_s: float | None = None
        self.sequence_id = 0
        self.warned_no_state = False
        self.warned_stale = False

        self.publisher = self.create_publisher(ChassisPosition, position_topic, 10)
        self.create_subscription(Float64MultiArray, state_topic, self.on_state, 10)
        self.timer = self.create_timer(1.0 / publish_rate_hz, self.on_timer)

        self.get_logger().info(
            "chassis_position_publisher ready: input=%s, output=%s, rate=%.1f Hz"
            % (state_topic, position_topic, publish_rate_hz)
        )

    def now_seconds(self) -> float:
        return self.get_clock().now().nanoseconds * 1.0e-9

    def on_state(self, msg: Float64MultiArray) -> None:
        if len(msg.data) < 2:
            self.get_logger().warning("Dropped chassis state with fewer than 2 values")
            return
        try:
            x = finite_float(msg.data[0], name="x")
            y = finite_float(msg.data[1], name="y")
        except ValueError as exc:
            self.get_logger().warning("Dropped invalid chassis state: %s" % exc)
            return
        self.latest_x = x
        self.latest_y = y
        self.latest_state_time_s = self.now_seconds()
        self.warned_no_state = False
        self.warned_stale = False

    def on_timer(self) -> None:
        if self.latest_x is None or self.latest_y is None or self.latest_state_time_s is None:
            if not self.warned_no_state:
                self.get_logger().warning("No chassis state received yet; not publishing position")
                self.warned_no_state = True
            return

        now_s = self.now_seconds()
        state_age_s = now_s - self.latest_state_time_s
        if state_age_s > self.max_state_age_s and not self.publish_stale_state:
            if not self.warned_stale:
                self.get_logger().warning(
                    "Latest chassis state is stale: age=%.3fs, max=%.3fs"
                    % (state_age_s, self.max_state_age_s)
                )
                self.warned_stale = True
            return

        msg = ChassisPosition()
        msg.publish_stamp = self.get_clock().now().to_msg()
        msg.sequence_id = self.sequence_id
        msg.x = self.latest_x
        msg.y = self.latest_y
        self.publisher.publish(msg)
        self.sequence_id = (self.sequence_id + 1) & 0xFFFFFFFF


def main() -> None:
    rclpy.init()
    node = ChassisPositionPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
