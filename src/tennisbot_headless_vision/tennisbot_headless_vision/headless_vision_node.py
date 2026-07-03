"""Headless stereo vision ROS node.

The node publishes only observations derived from real camera frames and a
recent chassis pose. It does not generate simulated target predictions.
"""

from __future__ import annotations

from collections import deque
import math
from pathlib import Path
import sys
from typing import Any, Callable, Optional

import rclpy
from rclpy._rclpy_pybind11 import RCLError
from builtin_interfaces.msg import Time
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from tennisbot_vision_msgs.msg import ChassisPose
from tennisbot_vision_msgs.msg import TargetPrediction

from .geometry import PoseSample, Transform3D, camera_point_to_field
from .trajectory import BallObservation, predict_target, seconds_to_duration


NANOSECONDS_PER_SECOND = 1_000_000_000


def time_to_nanoseconds(stamp: Time) -> int:
    return stamp.sec * NANOSECONDS_PER_SECOND + stamp.nanosec


def finite_float(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


class HeadlessVisionNode(Node):
    def __init__(self) -> None:
        super().__init__("headless_vision")

        self.declare_parameter("chassis_pose_topic", "/vision/chassis_pose")
        self.declare_parameter("target_prediction_topic", "/vision/target_prediction")
        self.declare_parameter("runtime_rate_hz", 30.0)
        self.declare_parameter("enable_camera", True)
        self.declare_parameter("dry_run", False)
        self.declare_parameter("stereo_tool_python_path", "tools/stereo/src")
        self.declare_parameter("left_device", "/dev/video0")
        self.declare_parameter("right_device", "/dev/video2")
        self.declare_parameter("width", 3840)
        self.declare_parameter("height", 2160)
        self.declare_parameter("fps", 30.0)
        self.declare_parameter("fourcc", "MJPG")
        self.declare_parameter("warmup_frames", 5)
        self.declare_parameter("calibration_package", "artifacts/calibration/stereo_cam1_cam2")
        self.declare_parameter("model_path", "artifacts/models/tennis_ball_yolo/model.pt")
        self.declare_parameter("conf", 0.05)
        self.declare_parameter("iou", 0.50)
        self.declare_parameter("imgsz", 1280)
        self.declare_parameter("max_detections", 6)
        self.declare_parameter("yolo_device", "")
        self.declare_parameter("class_id", 0)
        self.declare_parameter("tile", False)
        self.declare_parameter("tile_width", 2048)
        self.declare_parameter("tile_height", 1216)
        self.declare_parameter("tile_overlap", 160)
        self.declare_parameter("max_epipolar_error_px", 6.0)
        self.declare_parameter("min_disparity_px", 1.0)
        self.declare_parameter("max_disparity_px", 1200.0)
        self.declare_parameter("max_depth_m", 12.0)
        self.declare_parameter("camera_translation_m", [0.0, 0.0, 0.0])
        self.declare_parameter(
            "camera_rotation_rpy_rad",
            [-1.5707963267948966, 0.0, -1.5707963267948966],
        )
        self.declare_parameter("max_pose_age_s", 0.10)
        self.declare_parameter("pose_buffer_size", 90)
        self.declare_parameter("track_max_age_s", 0.60)
        self.declare_parameter("track_max_points", 24)
        self.declare_parameter("min_track_points", 3)
        self.declare_parameter("new_task_gap_s", 0.40)
        self.declare_parameter("target_plane_z", 0.6)
        self.declare_parameter("gravity_mps2", 9.80665)
        self.declare_parameter("min_predicted_time", 0.03)
        self.declare_parameter("max_predicted_time", 5.0)
        self.declare_parameter("min_sigma_m", 0.05)
        self.declare_parameter("max_abs_target_x", 15.0)
        self.declare_parameter("max_abs_target_y", 8.0)

        self._enable_camera = bool(self.get_parameter("enable_camera").value)
        self._dry_run = bool(self.get_parameter("dry_run").value)
        self._runtime_rate_hz = self._positive("runtime_rate_hz")
        self._max_pose_age_ns = int(self._positive("max_pose_age_s") * NANOSECONDS_PER_SECOND)
        self._track_max_age_ns = int(self._positive("track_max_age_s") * NANOSECONDS_PER_SECOND)
        self._new_task_gap_ns = int(self._positive("new_task_gap_s") * NANOSECONDS_PER_SECOND)
        self._track_max_points = self._positive_int("track_max_points")
        self._min_track_points = self._positive_int("min_track_points")
        self._target_plane_z = finite_float(
            self.get_parameter("target_plane_z").value,
            name="target_plane_z",
        )
        self._gravity_mps2 = self._positive("gravity_mps2")
        self._min_predicted_time = self._positive("min_predicted_time")
        self._max_predicted_time = self._positive("max_predicted_time")
        self._min_sigma_m = self._nonnegative("min_sigma_m")
        self._max_abs_target_x = self._positive("max_abs_target_x")
        self._max_abs_target_y = self._positive("max_abs_target_y")
        self._camera_transform = Transform3D(
            translation_m=self._float_vector("camera_translation_m", length=3),
            rotation_rpy_rad=self._float_vector("camera_rotation_rpy_rad", length=3),
        )

        pose_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=max(1, self._positive_int("pose_buffer_size")),
            reliability=ReliabilityPolicy.RELIABLE,
        )
        target_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self._target_publisher = self.create_publisher(
            TargetPrediction,
            str(self.get_parameter("target_prediction_topic").value),
            target_qos,
        )
        self.create_subscription(
            ChassisPose,
            str(self.get_parameter("chassis_pose_topic").value),
            self._pose_callback,
            pose_qos,
        )

        self._pose_buffer: deque[PoseSample] = deque(maxlen=max(1, self._positive_int("pose_buffer_size")))
        self._track: deque[BallObservation] = deque(maxlen=self._track_max_points)
        self._task_id = 1
        self._sequence_id = 0
        self._last_observation_ns: Optional[int] = None
        self._runtime: Optional[CameraRuntime] = None
        self._camera_failed = False
        self._last_wait_log_ns = 0

        self._timer = self.create_timer(1.0 / self._runtime_rate_hz, self._on_timer)
        self.get_logger().info(
            "headless vision ready: rate=%.1fHz camera=%s dry_run=%s target_topic=%s"
            % (
                self._runtime_rate_hz,
                self._enable_camera,
                self._dry_run,
                str(self.get_parameter("target_prediction_topic").value),
            )
        )

    def _pose_callback(self, msg: ChassisPose) -> None:
        try:
            pose = PoseSample(
                stamp_ns=time_to_nanoseconds(msg.stamp),
                x=finite_float(msg.x, name="pose x"),
                y=finite_float(msg.y, name="pose y"),
                z=finite_float(msg.z, name="pose z"),
                roll=finite_float(msg.roll, name="pose roll"),
                pitch=finite_float(msg.pitch, name="pose pitch"),
                yaw=finite_float(msg.yaw, name="pose yaw"),
            )
        except ValueError as exc:
            self.get_logger().warning(f"Dropped invalid chassis pose: {exc}")
            return
        self._pose_buffer.append(pose)

    def _on_timer(self) -> None:
        if self._dry_run or not self._enable_camera:
            self._log_waiting("headless vision camera runtime disabled; no predictions published")
            return
        if not self._pose_buffer:
            self._log_waiting("waiting for /vision/chassis_pose before opening camera runtime")
            return
        if self._camera_failed:
            return
        if self._runtime is None:
            try:
                self._runtime = CameraRuntime.from_node(self)
            except Exception as exc:  # noqa: BLE001 - keep ROS node alive after setup failures.
                self._camera_failed = True
                self.get_logger().error(f"camera runtime setup failed: {exc}")
                return

        try:
            sample = self._runtime.read_sample(self.get_clock().now)
        except Exception as exc:  # noqa: BLE001 - camera/runtime exceptions are external IO failures.
            self.get_logger().warning(f"dropped stereo frame: {exc}")
            return

        capture_ns = sample.capture_ns
        pose = self._closest_pose(capture_ns)
        if pose is None:
            self._log_waiting("dropping frame without a recent chassis pose")
            return

        field_point = camera_point_to_field(
            sample.point_camera_m,
            chassis_pose=pose,
            chassis_from_camera=self._camera_transform,
        )
        if self._last_observation_ns is None:
            self._track.clear()
        elif capture_ns - self._last_observation_ns > self._new_task_gap_ns:
            self._track.clear()
            self._task_id += 1
            self._sequence_id = 0

        self._track.append(
            BallObservation(
                stamp_ns=capture_ns,
                x=field_point.x,
                y=field_point.y,
                z=field_point.z,
                confidence=sample.confidence,
            )
        )
        self._last_observation_ns = capture_ns
        self._prune_track(capture_ns)
        if len(self._track) < self._min_track_points:
            return

        prediction = predict_target(
            list(self._track),
            target_plane_z=self._target_plane_z,
            gravity_mps2=self._gravity_mps2,
            min_time_s=self._min_predicted_time,
            max_time_s=self._max_predicted_time,
            min_sigma_m=self._min_sigma_m,
        )
        if prediction is None:
            return
        if (
            abs(prediction.target_x) > self._max_abs_target_x
            or abs(prediction.target_y) > self._max_abs_target_y
        ):
            self.get_logger().debug("dropped prediction outside configured target bounds")
            return

        msg = TargetPrediction()
        msg.capture_stamp = sample.capture_stamp
        msg.task_id = self._task_id
        msg.sequence_id = self._sequence_id
        msg.target_x = prediction.target_x
        msg.target_y = prediction.target_y
        msg.predicted_t_remain = seconds_to_duration(prediction.predicted_t_remain)
        msg.sigma_x = prediction.sigma_x
        msg.sigma_y = prediction.sigma_y
        self._target_publisher.publish(msg)
        self._sequence_id = (self._sequence_id + 1) & 0xFFFFFFFF

    def _closest_pose(self, stamp_ns: int) -> PoseSample | None:
        if not self._pose_buffer:
            return None
        closest = min(self._pose_buffer, key=lambda pose: abs(pose.stamp_ns - stamp_ns))
        return closest if abs(closest.stamp_ns - stamp_ns) <= self._max_pose_age_ns else None

    def _prune_track(self, now_ns: int) -> None:
        while self._track and now_ns - self._track[0].stamp_ns > self._track_max_age_ns:
            self._track.popleft()

    def _log_waiting(self, message: str) -> None:
        now_ns = self.get_clock().now().nanoseconds
        if now_ns - self._last_wait_log_ns >= NANOSECONDS_PER_SECOND:
            self.get_logger().info(message)
            self._last_wait_log_ns = now_ns

    def _positive(self, name: str) -> float:
        value = finite_float(self.get_parameter(name).value, name=name)
        if value <= 0.0:
            raise ValueError(f"parameter '{name}' must be positive")
        return value

    def _nonnegative(self, name: str) -> float:
        value = finite_float(self.get_parameter(name).value, name=name)
        if value < 0.0:
            raise ValueError(f"parameter '{name}' must be nonnegative")
        return value

    def _positive_int(self, name: str) -> int:
        value = int(self.get_parameter(name).value)
        if value <= 0:
            raise ValueError(f"parameter '{name}' must be positive")
        return value

    def _float_vector(self, name: str, *, length: int) -> tuple[float, ...]:
        value = self.get_parameter(name).value
        if not isinstance(value, (list, tuple)) or len(value) != length:
            raise ValueError(f"parameter '{name}' must be a list of {length} floats")
        result = tuple(finite_float(item, name=f"{name}[{index}]") for index, item in enumerate(value))
        return result


class StereoSample:
    def __init__(
        self,
        *,
        capture_stamp: Time,
        capture_ns: int,
        point_camera_m: tuple[float, float, float],
        confidence: float,
    ) -> None:
        self.capture_stamp = capture_stamp
        self.capture_ns = capture_ns
        self.point_camera_m = point_camera_m
        self.confidence = confidence


class CameraRuntime:
    def __init__(
        self,
        *,
        cv2_module: Any,
        left_capture: Any,
        right_capture: Any,
        calibration: Any,
        matcher: Any,
        detector: Any,
        calibration_package: Path,
        width: int,
        height: int,
    ) -> None:
        self.cv2 = cv2_module
        self.left_capture = left_capture
        self.right_capture = right_capture
        self.calibration = calibration
        self.matcher = matcher
        self.detector = detector
        self.calibration_package = calibration_package
        self.width = width
        self.height = height

    @classmethod
    def from_node(cls, node: HeadlessVisionNode) -> CameraRuntime:
        stereo_tool_path = Path(str(node.get_parameter("stereo_tool_python_path").value)).expanduser()
        if stereo_tool_path and stereo_tool_path.is_dir():
            resolved = str(stereo_tool_path.resolve())
            if resolved not in sys.path:
                sys.path.insert(0, resolved)

        import cv2  # noqa: PLC0415
        from tennisbot_stereo.calibration import RuntimeStereoCalibration  # noqa: PLC0415
        from tennisbot_stereo.detection import YoloBallDetector  # noqa: PLC0415
        from tennisbot_stereo.matching import StereoBallMatcher  # noqa: PLC0415

        width = int(node.get_parameter("width").value)
        height = int(node.get_parameter("height").value)
        fps = finite_float(node.get_parameter("fps").value, name="fps")
        fourcc = str(node.get_parameter("fourcc").value)
        if width <= 0 or height <= 0 or fps <= 0.0:
            raise ValueError("camera width, height, and fps must be positive")
        if len(fourcc) != 4:
            raise ValueError("fourcc must contain exactly four characters")

        calibration_package = Path(str(node.get_parameter("calibration_package").value)).expanduser()
        if not calibration_package.is_dir():
            raise FileNotFoundError(calibration_package)
        calibration = RuntimeStereoCalibration.from_package(
            calibration_package,
            frame_size=(width, height),
        )
        matcher = StereoBallMatcher(
            calibration,
            max_epipolar_error_px=finite_float(
                node.get_parameter("max_epipolar_error_px").value,
                name="max_epipolar_error_px",
            ),
            min_disparity_px=finite_float(
                node.get_parameter("min_disparity_px").value,
                name="min_disparity_px",
            ),
            max_disparity_px=finite_float(
                node.get_parameter("max_disparity_px").value,
                name="max_disparity_px",
            ),
            max_depth_m=finite_float(
                node.get_parameter("max_depth_m").value,
                name="max_depth_m",
            ),
        )
        model_path = Path(str(node.get_parameter("model_path").value)).expanduser()
        if not model_path.is_file():
            raise FileNotFoundError(model_path)
        device_value = str(node.get_parameter("yolo_device").value).strip()
        class_id = int(node.get_parameter("class_id").value)
        detector = YoloBallDetector(
            model_path,
            confidence_threshold=finite_float(node.get_parameter("conf").value, name="conf"),
            iou_threshold=finite_float(node.get_parameter("iou").value, name="iou"),
            imgsz=int(node.get_parameter("imgsz").value),
            max_detections=int(node.get_parameter("max_detections").value),
            device=device_value or None,
            class_id=None if class_id < 0 else class_id,
            tile=bool(node.get_parameter("tile").value),
            tile_width=int(node.get_parameter("tile_width").value),
            tile_height=int(node.get_parameter("tile_height").value),
            tile_overlap=int(node.get_parameter("tile_overlap").value),
        )

        left = open_capture(
            cv2,
            str(node.get_parameter("left_device").value),
            width,
            height,
            fps,
            fourcc,
        )
        right = open_capture(
            cv2,
            str(node.get_parameter("right_device").value),
            width,
            height,
            fps,
            fourcc,
        )
        for _ in range(max(0, int(node.get_parameter("warmup_frames").value))):
            left.read()
            right.read()

        node.get_logger().info(
            "camera runtime opened: left=%s right=%s %dx%d@%.1f detector=%s"
            % (
                str(node.get_parameter("left_device").value),
                str(node.get_parameter("right_device").value),
                width,
                height,
                fps,
                "yolo",
            )
        )
        return cls(
            cv2_module=cv2,
            left_capture=left,
            right_capture=right,
            calibration=calibration,
            matcher=matcher,
            detector=detector,
            calibration_package=calibration_package,
            width=width,
            height=height,
        )

    def read_sample(self, stamp_factory: Callable[[], Any]) -> StereoSample:
        left_ok, left_frame = self.left_capture.read()
        right_ok, right_frame = self.right_capture.read()
        capture_time = stamp_factory()
        if not left_ok or not right_ok:
            raise RuntimeError(f"camera read failed: left_ok={left_ok} right_ok={right_ok}")
        if left_frame.shape[:2] != right_frame.shape[:2]:
            raise RuntimeError(
                f"stereo frame sizes differ: left={left_frame.shape[:2]} right={right_frame.shape[:2]}"
            )

        actual_size = (int(left_frame.shape[1]), int(left_frame.shape[0]))
        if actual_size != self.calibration.image_size:
            from tennisbot_stereo.calibration import RuntimeStereoCalibration  # noqa: PLC0415

            self.calibration = RuntimeStereoCalibration.from_package(
                self.calibration_package,
                frame_size=actual_size,
            )
            self.matcher.calibration = self.calibration

        left_detections, right_detections = self.detector.detect_pair(left_frame, right_frame)
        match = self.matcher.select(left_detections, right_detections)
        if match is None:
            raise RuntimeError("no valid stereo ball match")
        point = match.point_3d_m
        return StereoSample(
            capture_stamp=capture_time.to_msg(),
            capture_ns=int(capture_time.nanoseconds),
            point_camera_m=(float(point[0]), float(point[1]), float(point[2])),
            confidence=float(match.confidence),
        )


def open_capture(
    cv2_module: Any,
    device: str,
    width: int,
    height: int,
    fps: float,
    fourcc: str,
) -> Any:
    source: int | str = int(device) if device.isdecimal() else device
    capture = cv2_module.VideoCapture(source, cv2_module.CAP_V4L2)
    if not capture.isOpened():
        raise RuntimeError(f"cannot open camera device: {device}")
    capture.set(cv2_module.CAP_PROP_FOURCC, cv2_module.VideoWriter_fourcc(*fourcc))
    capture.set(cv2_module.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2_module.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2_module.CAP_PROP_FPS, fps)
    return capture


def main(args=None) -> None:
    rclpy.init(args=args)
    node = HeadlessVisionNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, RCLError):
        pass
    finally:
        if node._runtime is not None:
            node._runtime.left_capture.release()
            node._runtime.right_capture.release()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
