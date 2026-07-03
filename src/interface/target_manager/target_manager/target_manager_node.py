"""Manage 30 Hz vision predictions before they reach the trajectory planner."""

from collections import deque
from dataclasses import dataclass
import math
from typing import Deque, Optional

import rclpy
from builtin_interfaces.msg import Duration
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from target_msgs.msg import ManagedTarget, RawTarget


NANOSECONDS_PER_SECOND = 1_000_000_000


def time_to_nanoseconds(stamp) -> int:
    return stamp.sec * NANOSECONDS_PER_SECOND + stamp.nanosec


def duration_to_nanoseconds(duration: Duration) -> int:
    return duration.sec * NANOSECONDS_PER_SECOND + duration.nanosec


def nanoseconds_to_duration(value: int) -> Duration:
    value = max(0, int(value))
    msg = Duration()
    msg.sec = value // NANOSECONDS_PER_SECOND
    msg.nanosec = value % NANOSECONDS_PER_SECOND
    return msg


@dataclass(frozen=True)
class TargetSample:
    sequence_id: int
    target_x: float
    target_y: float
    landing_time_ns: int
    sigma_x: float
    sigma_y: float


class TargetManager(Node):
    """Single ROS node implementing the target interface layer."""

    def __init__(self) -> None:
        super().__init__("target_manager")

        self.declare_parameter("raw_topic", "/target/raw")
        self.declare_parameter("managed_topic", "/target/managed")
        self.declare_parameter("buffer_size", 15)
        self.declare_parameter("max_output_rate", 10.0)
        self.declare_parameter("noise_deadband", 0.03)
        self.declare_parameter("replan_distance", 0.08)
        self.declare_parameter("large_jump_distance", 0.50)
        self.declare_parameter("jump_confirm_radius", 0.10)
        self.declare_parameter("jump_confirm_frames", 3)
        self.declare_parameter("stable_window_size", 5)
        self.declare_parameter("stable_range_x", 0.05)
        self.declare_parameter("stable_range_y", 0.05)
        self.declare_parameter("sigma_reference", 0.10)
        self.declare_parameter("alpha_min", 0.15)
        self.declare_parameter("alpha_max", 0.85)
        self.declare_parameter("deadband_alpha_scale", 0.50)
        self.declare_parameter("future_stamp_tolerance", 0.02)
        self.declare_parameter("max_predicted_time", 5.0)
        self.declare_parameter("max_abs_target_x", 15.0)
        self.declare_parameter("max_abs_target_y", 8.0)

        self._buffer_size = self._positive_int("buffer_size")
        self._max_output_rate = self._positive("max_output_rate")
        self._min_output_interval_ns = int(
            NANOSECONDS_PER_SECOND / self._max_output_rate
        )
        self._noise_deadband = self._nonnegative("noise_deadband")
        self._replan_distance = self._positive("replan_distance")
        self._large_jump_distance = self._positive("large_jump_distance")
        self._jump_confirm_radius = self._positive("jump_confirm_radius")
        self._jump_confirm_frames = self._positive_int("jump_confirm_frames")
        self._stable_window_size = self._positive_int("stable_window_size")
        self._stable_range_x = self._nonnegative("stable_range_x")
        self._stable_range_y = self._nonnegative("stable_range_y")
        self._sigma_reference = self._positive("sigma_reference")
        self._alpha_min = self._unit_interval("alpha_min")
        self._alpha_max = self._unit_interval("alpha_max")
        self._deadband_alpha_scale = self._unit_interval("deadband_alpha_scale")
        self._future_tolerance_ns = int(
            self._nonnegative("future_stamp_tolerance") * NANOSECONDS_PER_SECOND
        )
        self._max_predicted_time_ns = int(
            self._positive("max_predicted_time") * NANOSECONDS_PER_SECOND
        )
        self._max_abs_target_x = self._positive("max_abs_target_x")
        self._max_abs_target_y = self._positive("max_abs_target_y")

        if self._alpha_min > self._alpha_max:
            raise ValueError("alpha_min cannot be greater than alpha_max")
        if self._stable_window_size > self._buffer_size:
            raise ValueError("stable_window_size cannot exceed buffer_size")
        if self._replan_distance < self._noise_deadband:
            raise ValueError("replan_distance cannot be smaller than noise_deadband")
        if self._large_jump_distance <= self._replan_distance:
            raise ValueError(
                "large_jump_distance must be greater than replan_distance"
            )

        self._samples: Deque[TargetSample] = deque(maxlen=self._buffer_size)
        self._current_task_id: Optional[int] = None
        self._last_sequence_id: Optional[int] = None
        self._filtered_x: Optional[float] = None
        self._filtered_y: Optional[float] = None
        self._last_output_x: Optional[float] = None
        self._last_output_y: Optional[float] = None
        self._last_output_time_ns: Optional[int] = None
        self._last_stable = False

        self._jump_samples: Deque[TargetSample] = deque(
            maxlen=self._jump_confirm_frames
        )

        input_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        output_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._publisher = self.create_publisher(
            ManagedTarget,
            str(self.get_parameter("managed_topic").value),
            output_qos,
        )
        self.create_subscription(
            RawTarget,
            str(self.get_parameter("raw_topic").value),
            self._target_callback,
            input_qos,
        )

        self.get_logger().info(
            "Target manager ready: input=30 Hz expected, "
            f"output<={self._max_output_rate:.1f} Hz, "
            f"buffer={self._buffer_size} frames"
        )

    def _target_callback(self, msg: RawTarget) -> None:
        receive_time_ns = self.get_clock().now().nanoseconds

        sample = self._validate_and_convert(msg, receive_time_ns)
        if sample is None:
            return

        is_new_task = self._handle_task_and_sequence(msg.task_id, msg.sequence_id)
        if is_new_task is None:
            return
        if is_new_task:
            self._reset_task(msg.task_id)
            self._last_sequence_id = msg.sequence_id
            self._accept_first_sample(sample)
            self._publish(sample, stable=False, force=True)
            return

        self._last_sequence_id = msg.sequence_id
        self._samples.append(sample)

        jump_confirmed = self._update_filter(sample)
        stable = self._is_stable()
        stable_changed_to_true = stable and not self._last_stable

        filtered_change = self._distance(
            self._filtered_x,
            self._filtered_y,
            self._last_output_x,
            self._last_output_y,
        )
        enough_time_since_output = (
            self._last_output_time_ns is None
            or receive_time_ns - self._last_output_time_ns
            >= self._min_output_interval_ns
        )
        target_changed = filtered_change >= self._replan_distance

        should_publish = jump_confirmed or stable_changed_to_true
        if target_changed and enough_time_since_output:
            should_publish = True

        published = False
        if should_publish and enough_time_since_output:
            published = self._publish(
                sample,
                stable=stable,
                force=False,
            )
        if not stable:
            self._last_stable = False
        elif published:
            self._last_stable = True

    def _validate_and_convert(
        self,
        msg: RawTarget,
        receive_time_ns: int,
    ) -> Optional[TargetSample]:
        values = (msg.target_x, msg.target_y, msg.sigma_x, msg.sigma_y)
        if not all(math.isfinite(value) for value in values):
            self.get_logger().warning("Dropped target with non-finite values")
            return None
        if msg.sigma_x < 0.0 or msg.sigma_y < 0.0:
            self.get_logger().warning("Dropped target with negative sigma")
            return None
        if (
            abs(msg.target_x) > self._max_abs_target_x
            or abs(msg.target_y) > self._max_abs_target_y
        ):
            self.get_logger().warning("Dropped target outside configured court bounds")
            return None

        capture_time_ns = time_to_nanoseconds(msg.capture_stamp)
        if capture_time_ns > receive_time_ns + self._future_tolerance_ns:
            self.get_logger().warning("Dropped target with capture time in the future")
            return None

        predicted_ns = duration_to_nanoseconds(msg.predicted_t_remain)
        if predicted_ns <= 0 or predicted_ns > self._max_predicted_time_ns:
            self.get_logger().warning("Dropped target with invalid predicted_t_remain")
            return None

        landing_time_ns = capture_time_ns + predicted_ns
        if landing_time_ns <= receive_time_ns:
            self.get_logger().debug("Dropped expired target prediction")
            return None

        return TargetSample(
            sequence_id=msg.sequence_id,
            target_x=msg.target_x,
            target_y=msg.target_y,
            landing_time_ns=landing_time_ns,
            sigma_x=msg.sigma_x,
            sigma_y=msg.sigma_y,
        )

    def _handle_task_and_sequence(
        self,
        task_id: int,
        sequence_id: int,
    ) -> Optional[bool]:
        if self._current_task_id is None:
            return True
        if task_id < self._current_task_id:
            self.get_logger().debug("Dropped delayed message from an older task")
            return None
        if task_id > self._current_task_id:
            return True
        if self._last_sequence_id is not None and sequence_id <= self._last_sequence_id:
            self.get_logger().debug("Dropped duplicate or out-of-order sequence")
            return None
        return False

    def _reset_task(self, task_id: int) -> None:
        self._current_task_id = task_id
        self._samples.clear()
        self._jump_samples.clear()
        self._filtered_x = None
        self._filtered_y = None
        self._last_output_x = None
        self._last_output_y = None
        self._last_output_time_ns = None
        self._last_stable = False
        self.get_logger().info(f"Started target task {task_id}")

    def _accept_first_sample(self, sample: TargetSample) -> None:
        self._samples.append(sample)
        self._filtered_x = sample.target_x
        self._filtered_y = sample.target_y

    def _update_filter(self, sample: TargetSample) -> bool:
        distance = self._distance(
            sample.target_x,
            sample.target_y,
            self._filtered_x,
            self._filtered_y,
        )

        if distance >= self._large_jump_distance:
            return self._process_large_jump(sample)

        self._jump_samples.clear()
        alpha_x = self._filter_alpha(sample.sigma_x)
        alpha_y = self._filter_alpha(sample.sigma_y)
        if distance < self._noise_deadband:
            alpha_x *= self._deadband_alpha_scale
            alpha_y *= self._deadband_alpha_scale
        self._filtered_x += alpha_x * (sample.target_x - self._filtered_x)
        self._filtered_y += alpha_y * (sample.target_y - self._filtered_y)
        return False

    def _process_large_jump(self, sample: TargetSample) -> bool:
        if not self._jump_samples:
            self._jump_samples.append(sample)
            return False

        candidate_x = sum(item.target_x for item in self._jump_samples) / len(
            self._jump_samples
        )
        candidate_y = sum(item.target_y for item in self._jump_samples) / len(
            self._jump_samples
        )
        if (
            self._distance(
                sample.target_x,
                sample.target_y,
                candidate_x,
                candidate_y,
            )
            > self._jump_confirm_radius
        ):
            self._jump_samples.clear()
            self._jump_samples.append(sample)
            return False

        self._jump_samples.append(sample)
        if len(self._jump_samples) < self._jump_confirm_frames:
            return False

        self._filtered_x = sum(
            item.target_x for item in self._jump_samples
        ) / len(self._jump_samples)
        self._filtered_y = sum(
            item.target_y for item in self._jump_samples
        ) / len(self._jump_samples)
        self._jump_samples.clear()
        self.get_logger().info("Accepted a confirmed large target correction")
        return True

    def _filter_alpha(self, sigma: float) -> float:
        """Convert vision uncertainty into a new-sample filter weight.

        sigma == sigma_reference gives alpha=0.5. A smaller sigma trusts the
        new prediction more; a larger sigma trusts the existing estimate more.
        """
        raw_alpha = self._sigma_reference / (sigma + self._sigma_reference)
        return max(self._alpha_min, min(raw_alpha, self._alpha_max))

    def _is_stable(self) -> bool:
        if self._jump_samples:
            return False
        if len(self._samples) < self._stable_window_size:
            return False
        recent = list(self._samples)[-self._stable_window_size :]
        x_values = [item.target_x for item in recent]
        y_values = [item.target_y for item in recent]
        return (
            max(x_values) - min(x_values) <= self._stable_range_x
            and max(y_values) - min(y_values) <= self._stable_range_y
        )

    def _publish(
        self,
        source: TargetSample,
        stable: bool,
        force: bool,
    ) -> bool:
        now = self.get_clock().now()
        now_ns = now.nanoseconds
        real_t_remain_ns = source.landing_time_ns - now_ns
        if real_t_remain_ns <= 0:
            return False
        if (
            not force
            and self._last_output_time_ns is not None
            and now_ns - self._last_output_time_ns < self._min_output_interval_ns
        ):
            return False

        msg = ManagedTarget()
        msg.update_stamp = now.to_msg()
        msg.task_id = self._current_task_id
        msg.sequence_id = source.sequence_id
        msg.target_x = self._filtered_x
        msg.target_y = self._filtered_y
        msg.real_t_remain = nanoseconds_to_duration(real_t_remain_ns)
        msg.sigma_x = source.sigma_x
        msg.sigma_y = source.sigma_y
        msg.stable = stable
        self._publisher.publish(msg)

        self._last_output_x = self._filtered_x
        self._last_output_y = self._filtered_y
        self._last_output_time_ns = now_ns
        return True

    @staticmethod
    def _distance(x1, y1, x2, y2) -> float:
        if None in (x1, y1, x2, y2):
            return math.inf
        return math.hypot(x1 - x2, y1 - y2)

    def _positive(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if value <= 0.0:
            raise ValueError(f"parameter '{name}' must be positive")
        return value

    def _nonnegative(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if value < 0.0:
            raise ValueError(f"parameter '{name}' must be nonnegative")
        return value

    def _positive_int(self, name: str) -> int:
        value = int(self.get_parameter(name).value)
        if value <= 0:
            raise ValueError(f"parameter '{name}' must be a positive integer")
        return value

    def _unit_interval(self, name: str) -> float:
        value = float(self.get_parameter(name).value)
        if not 0.0 < value <= 1.0:
            raise ValueError(f"parameter '{name}' must be in (0, 1]")
        return value


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TargetManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
