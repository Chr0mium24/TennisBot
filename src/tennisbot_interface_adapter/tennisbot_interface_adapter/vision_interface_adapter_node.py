"""Bridge TennisBot vision topics to the external target interface."""

from __future__ import annotations

import math
from typing import Optional

import rclpy
from builtin_interfaces.msg import Duration, Time
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import Float64MultiArray
from target_msgs.msg import ChassisPosition as InterfaceChassisPosition
from target_msgs.msg import RawTarget
from tennisbot_vision_msgs.msg import ChassisPosition as VisionChassisPosition
from tennisbot_vision_msgs.msg import ChassisPose as VisionChassisPose
from tennisbot_vision_msgs.msg import TargetPrediction


NANOSECONDS_PER_SECOND = 1_000_000_000


def time_to_nanoseconds(stamp: Time) -> int:
    return stamp.sec * NANOSECONDS_PER_SECOND + stamp.nanosec


def duration_to_nanoseconds(duration: Duration) -> int:
    return duration.sec * NANOSECONDS_PER_SECOND + duration.nanosec


def finite_float(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def normalize_angle(angle_rad: float) -> float:
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi


class VisionInterfaceAdapter(Node):
    """Adapter between repository-owned vision topics and imported interface topics."""

    def __init__(self) -> None:
        super().__init__("vision_interface_adapter")

        self.declare_parameter("interface_chassis_topic", "/robot/chassis_position")
        self.declare_parameter("interface_chassis_state_topic", "/robot/chassis_state")
        self.declare_parameter("interface_raw_target_topic", "/target/raw")
        self.declare_parameter("vision_chassis_topic", "/vision/chassis_position")
        self.declare_parameter("vision_chassis_pose_topic", "/vision/chassis_pose")
        self.declare_parameter("vision_target_topic", "/vision/target_prediction")
        self.declare_parameter("forward_chassis_position", True)
        self.declare_parameter("forward_chassis_pose", True)
        self.declare_parameter("forward_target_prediction", True)
        self.declare_parameter("chassis_state_input_frame", "field")
        self.declare_parameter("max_chassis_rate_hz", 30.0)
        self.declare_parameter("max_chassis_pose_rate_hz", 30.0)
        self.declare_parameter("max_target_rate_hz", 30.0)
        self.declare_parameter("rate_limit_slack", 0.10)
        self.declare_parameter("future_stamp_tolerance", 0.02)
        self.declare_parameter("max_predicted_time", 5.0)
        self.declare_parameter("max_abs_target_x", 15.0)
        self.declare_parameter("max_abs_target_y", 8.0)

        self._forward_chassis_position = bool(
            self.get_parameter("forward_chassis_position").value
        )
        self._forward_chassis_pose = bool(
            self.get_parameter("forward_chassis_pose").value
        )
        self._forward_target_prediction = bool(
            self.get_parameter("forward_target_prediction").value
        )
        self._chassis_min_interval_ns = self._min_interval_ns(
            "max_chassis_rate_hz"
        )
        self._chassis_pose_min_interval_ns = self._min_interval_ns(
            "max_chassis_pose_rate_hz"
        )
        self._target_min_interval_ns = self._min_interval_ns("max_target_rate_hz")
        self._chassis_state_input_frame = self._frame_parameter(
            "chassis_state_input_frame"
        )
        self._future_tolerance_ns = int(
            self._nonnegative("future_stamp_tolerance") * NANOSECONDS_PER_SECOND
        )
        self._max_predicted_time_ns = int(
            self._positive("max_predicted_time") * NANOSECONDS_PER_SECOND
        )
        self._max_abs_target_x = self._positive("max_abs_target_x")
        self._max_abs_target_y = self._positive("max_abs_target_y")

        self._last_chassis_publish_ns: Optional[int] = None
        self._last_chassis_pose_publish_ns: Optional[int] = None
        self._last_target_publish_ns: Optional[int] = None
        self._chassis_pose_sequence_id = 0

        input_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        output_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
        )

        if self._forward_chassis_position:
            self._vision_chassis_publisher = self.create_publisher(
                VisionChassisPosition,
                str(self.get_parameter("vision_chassis_topic").value),
                output_qos,
            )
            self.create_subscription(
                InterfaceChassisPosition,
                str(self.get_parameter("interface_chassis_topic").value),
                self._chassis_callback,
                input_qos,
            )
        else:
            self._vision_chassis_publisher = None

        if self._forward_chassis_pose:
            self._vision_chassis_pose_publisher = self.create_publisher(
                VisionChassisPose,
                str(self.get_parameter("vision_chassis_pose_topic").value),
                output_qos,
            )
            self.create_subscription(
                Float64MultiArray,
                str(self.get_parameter("interface_chassis_state_topic").value),
                self._chassis_state_callback,
                input_qos,
            )
        else:
            self._vision_chassis_pose_publisher = None

        if self._forward_target_prediction:
            self._interface_target_publisher = self.create_publisher(
                RawTarget,
                str(self.get_parameter("interface_raw_target_topic").value),
                output_qos,
            )
            self.create_subscription(
                TargetPrediction,
                str(self.get_parameter("vision_target_topic").value),
                self._target_callback,
                input_qos,
            )
        else:
            self._interface_target_publisher = None

        self.get_logger().info(
            "vision interface adapter ready: "
            f"chassis_forward={self._forward_chassis_position}, "
            f"pose_forward={self._forward_chassis_pose}, "
            f"target_forward={self._forward_target_prediction}"
        )

    def _chassis_callback(self, msg: InterfaceChassisPosition) -> None:
        now_ns = self.get_clock().now().nanoseconds
        if not self._can_publish(
            now_ns,
            self._last_chassis_publish_ns,
            self._chassis_min_interval_ns,
        ):
            return
        try:
            x = finite_float(msg.x, name="chassis x")
            y = finite_float(msg.y, name="chassis y")
        except ValueError as exc:
            self.get_logger().warning(f"Dropped invalid chassis position: {exc}")
            return

        out = VisionChassisPosition()
        out.stamp = msg.publish_stamp
        out.sequence_id = msg.sequence_id
        out.x = x
        out.y = y
        self._vision_chassis_publisher.publish(out)
        self._last_chassis_publish_ns = now_ns

    def _chassis_state_callback(self, msg: Float64MultiArray) -> None:
        now = self.get_clock().now()
        now_ns = now.nanoseconds
        if not self._can_publish(
            now_ns,
            self._last_chassis_pose_publish_ns,
            self._chassis_pose_min_interval_ns,
        ):
            return
        if len(msg.data) < 5:
            self.get_logger().warning(
                "Dropped chassis state with fewer than 5 values; need x,y,v,phi,yaw"
            )
            return

        try:
            raw_x = finite_float(msg.data[0], name="chassis state x")
            raw_y = finite_float(msg.data[1], name="chassis state y")
            linear_velocity = finite_float(
                msg.data[2],
                name="chassis state linear velocity",
            )
            yaw = finite_float(msg.data[4], name="chassis state yaw")
            ground_speed = (
                finite_float(msg.data[5], name="chassis state ground speed")
                if len(msg.data) > 5
                else linear_velocity
            )
        except ValueError as exc:
            self.get_logger().warning(f"Dropped invalid chassis state: {exc}")
            return

        x = raw_x
        y = raw_y
        if self._chassis_state_input_frame == "cartesian":
            x = raw_y
            y = -raw_x
            yaw = normalize_angle(yaw - math.pi / 2.0)

        out = VisionChassisPose()
        out.stamp = now.to_msg()
        out.sequence_id = self._chassis_pose_sequence_id
        out.x = x
        out.y = y
        out.z = 0.0
        out.roll = 0.0
        out.pitch = 0.0
        out.yaw = yaw
        out.linear_velocity = linear_velocity
        out.ground_speed = ground_speed
        self._vision_chassis_pose_publisher.publish(out)
        self._last_chassis_pose_publish_ns = now_ns
        self._chassis_pose_sequence_id = (self._chassis_pose_sequence_id + 1) & 0xFFFFFFFF

    def _target_callback(self, msg: TargetPrediction) -> None:
        now_ns = self.get_clock().now().nanoseconds
        if not self._can_publish(
            now_ns,
            self._last_target_publish_ns,
            self._target_min_interval_ns,
        ):
            return
        if not self._target_is_valid(msg, now_ns):
            return

        out = RawTarget()
        out.capture_stamp = msg.capture_stamp
        out.task_id = msg.task_id
        out.sequence_id = msg.sequence_id
        out.target_x = msg.target_x
        out.target_y = msg.target_y
        out.predicted_t_remain = msg.predicted_t_remain
        out.sigma_x = msg.sigma_x
        out.sigma_y = msg.sigma_y
        self._interface_target_publisher.publish(out)
        self._last_target_publish_ns = now_ns

    def _target_is_valid(self, msg: TargetPrediction, now_ns: int) -> bool:
        values = (msg.target_x, msg.target_y, msg.sigma_x, msg.sigma_y)
        if not all(math.isfinite(value) for value in values):
            self.get_logger().warning("Dropped target prediction with non-finite values")
            return False
        if msg.sigma_x < 0.0 or msg.sigma_y < 0.0:
            self.get_logger().warning("Dropped target prediction with negative sigma")
            return False
        if (
            abs(msg.target_x) > self._max_abs_target_x
            or abs(msg.target_y) > self._max_abs_target_y
        ):
            self.get_logger().warning("Dropped target prediction outside court bounds")
            return False

        capture_time_ns = time_to_nanoseconds(msg.capture_stamp)
        if capture_time_ns > now_ns + self._future_tolerance_ns:
            self.get_logger().warning("Dropped target prediction with future capture time")
            return False

        predicted_ns = duration_to_nanoseconds(msg.predicted_t_remain)
        if predicted_ns <= 0 or predicted_ns > self._max_predicted_time_ns:
            self.get_logger().warning("Dropped target prediction with invalid remaining time")
            return False
        return True

    def _min_interval_ns(self, parameter_name: str) -> Optional[int]:
        rate_hz = float(self.get_parameter(parameter_name).value)
        if not math.isfinite(rate_hz):
            raise ValueError(f"parameter '{parameter_name}' must be finite")
        if rate_hz <= 0.0:
            return None
        slack = self._unit_interval_inclusive_zero("rate_limit_slack")
        interval = NANOSECONDS_PER_SECOND / rate_hz
        return int(interval * max(0.0, 1.0 - slack))

    @staticmethod
    def _can_publish(
        now_ns: int,
        last_publish_ns: Optional[int],
        min_interval_ns: Optional[int],
    ) -> bool:
        if min_interval_ns is None or last_publish_ns is None:
            return True
        return now_ns - last_publish_ns >= min_interval_ns

    def _positive(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if not math.isfinite(value) or value <= 0.0:
            raise ValueError(f"parameter '{name}' must be positive")
        return value

    def _nonnegative(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError(f"parameter '{name}' must be nonnegative")
        return value

    def _unit_interval_inclusive_zero(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if not math.isfinite(value) or not 0.0 <= value < 1.0:
            raise ValueError(f"parameter '{name}' must be in [0, 1)")
        return value

    def _frame_parameter(self, name: str) -> str:
        value = str(self.get_parameter(name).value).strip().lower()
        if value not in {"field", "cartesian"}:
            raise ValueError(f"parameter '{name}' must be 'field' or 'cartesian'")
        return value


def main(args=None) -> None:
    rclpy.init(args=args)
    node = VisionInterfaceAdapter()
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
