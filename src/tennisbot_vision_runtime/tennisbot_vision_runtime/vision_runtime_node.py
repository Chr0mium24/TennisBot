"""Vision runtime node.

The node publishes only observations derived from real camera frames and a
recent chassis pose. It does not generate simulated target predictions.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime
import json
import math
from pathlib import Path
import sys
from typing import Any, Callable, Optional, TextIO

import rclpy
from rclpy._rclpy_pybind11 import RCLError
from builtin_interfaces.msg import Time
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from target_msgs.msg import ChassisPosition, RawTarget

from .geometry import PoseSample, Transform3D, camera_point_to_field
from .trajectory import BallObservation, predict_target, seconds_to_duration


NANOSECONDS_PER_SECOND = 1_000_000_000


def finite_float(value: object, *, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


class VisionRuntimeNode(Node):
    def __init__(self) -> None:
        super().__init__("vision_runtime")

        self.declare_parameter("chassis_position_topic", "/robot/chassis_position")
        self.declare_parameter("raw_target_topic", "/target/raw")
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
        self.declare_parameter("initial_task_id", 1)
        self.declare_parameter("single_task_mode", False)
        self.declare_parameter("single_task_shutdown_on_complete", True)
        self.declare_parameter("target_plane_z", 0.6)
        self.declare_parameter("gravity_mps2", 9.80665)
        self.declare_parameter("min_predicted_time", 0.03)
        self.declare_parameter("max_predicted_time", 5.0)
        self.declare_parameter("min_sigma_m", 0.05)
        self.declare_parameter("max_abs_target_x", 15.0)
        self.declare_parameter("max_abs_target_y", 8.0)
        self.declare_parameter("runtime_log_enabled", False)
        self.declare_parameter("runtime_log_root", "runs/vision-runtime")
        self.declare_parameter("runtime_log_session", "")
        self.declare_parameter("runtime_log_video", True)
        self.declare_parameter("runtime_log_chassis", True)
        self.declare_parameter("runtime_log_yolo", True)
        self.declare_parameter("runtime_log_targets", True)
        self.declare_parameter("runtime_log_events", True)
        self.declare_parameter("runtime_log_video_fourcc", "mp4v")

        self._enable_camera = bool(self.get_parameter("enable_camera").value)
        self._dry_run = bool(self.get_parameter("dry_run").value)
        self._runtime_rate_hz = self._positive("runtime_rate_hz")
        self._single_task_mode = bool(self.get_parameter("single_task_mode").value)
        self._single_task_shutdown_on_complete = bool(
            self.get_parameter("single_task_shutdown_on_complete").value
        )
        self._single_task_complete = False
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
        self._runtime_logger = RuntimeRunLogger.from_node(self)

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
            RawTarget,
            str(self.get_parameter("raw_target_topic").value),
            target_qos,
        )
        self.create_subscription(
            ChassisPosition,
            str(self.get_parameter("chassis_position_topic").value),
            self._chassis_position_callback,
            pose_qos,
        )

        self._pose_buffer: deque[PoseSample] = deque(maxlen=max(1, self._positive_int("pose_buffer_size")))
        self._track: deque[BallObservation] = deque(maxlen=self._track_max_points)
        self._task_id = self._positive_int("initial_task_id")
        self._sequence_id = 0
        self._last_observation_ns: Optional[int] = None
        self._runtime: Optional[CameraRuntime] = None
        self._camera_failed = False
        self._last_wait_log_ns = 0

        self._timer = self.create_timer(1.0 / self._runtime_rate_hz, self._on_timer)
        self.get_logger().info(
            "vision runtime ready: rate=%.1fHz camera=%s dry_run=%s task_id=%d raw_target_topic=%s"
            % (
                self._runtime_rate_hz,
                self._enable_camera,
                self._dry_run,
                self._task_id,
                str(self.get_parameter("raw_target_topic").value),
            )
        )
        self._runtime_logger.record_event(
            "vision_runtime_ready",
            {
                "runtime_rate_hz": self._runtime_rate_hz,
                "enable_camera": self._enable_camera,
                "dry_run": self._dry_run,
                "initial_task_id": self._task_id,
                "single_task_mode": self._single_task_mode,
                "raw_target_topic": str(self.get_parameter("raw_target_topic").value),
            },
        )

    def _chassis_position_callback(self, msg: ChassisPosition) -> None:
        try:
            raw_x = finite_float(msg.x, name="chassis position x")
            raw_y = finite_float(msg.y, name="chassis position y")
            raw_yaw = finite_float(msg.yaw, name="chassis position yaw")
            pose = PoseSample(
                stamp_ns=time_to_nanoseconds(msg.publish_stamp),
                x=raw_x,
                y=raw_y,
                z=0.0,
                roll=0.0,
                pitch=0.0,
                yaw=raw_yaw,
            )
        except ValueError as exc:
            self.get_logger().warning(f"Dropped invalid chassis position: {exc}")
            return
        self._pose_buffer.append(pose)
        self._runtime_logger.record_chassis(
            stamp=msg.publish_stamp,
            source={
                "sequence_id": int(msg.sequence_id),
                "x": raw_x,
                "y": raw_y,
                "yaw": raw_yaw,
            },
            pose=pose,
        )

    def _on_timer(self) -> None:
        if self._single_task_complete:
            return
        if self._dry_run or not self._enable_camera:
            self._log_waiting("vision runtime camera disabled; no predictions published")
            return
        if not self._pose_buffer:
            self._log_waiting("waiting for /robot/chassis_position before opening camera runtime")
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
            self._runtime_logger.record_event("dropped_stereo_frame", {"reason": str(exc)})
            self._complete_single_task_if_gap(self.get_clock().now().nanoseconds)
            return

        capture_ns = sample.capture_ns
        pose, closest_pose, pose_delta_ns = self._closest_pose_with_delta(capture_ns)
        if pose is None:
            self._runtime_logger.record_event(
                "dropped_frame_without_recent_pose",
                {
                    "frame_id": int(sample.frame_id),
                    "capture_stamp": stamp_to_dict(sample.capture_stamp),
                    "capture_ns": int(capture_ns),
                    "closest_pose_ns": None if closest_pose is None else int(closest_pose.stamp_ns),
                    "pose_delta_s": None
                    if pose_delta_ns is None
                    else float(pose_delta_ns / NANOSECONDS_PER_SECOND),
                    "pose_abs_age_s": None
                    if pose_delta_ns is None
                    else float(abs(pose_delta_ns) / NANOSECONDS_PER_SECOND),
                    "max_pose_age_s": float(self._max_pose_age_ns / NANOSECONDS_PER_SECOND),
                    "pose_buffer_size": int(len(self._pose_buffer)),
                },
            )
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
            if self._single_task_mode:
                self._complete_single_task("new_observation_after_task_gap", capture_ns)
                return
            self._track.clear()
            self._task_id += 1
            self._sequence_id = 0

        self._runtime_logger.record_observation(
            frame_id=sample.frame_id,
            capture_stamp=sample.capture_stamp,
            point_camera_m=sample.point_camera_m,
            field_point=field_point,
            confidence=sample.confidence,
        )
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

        msg = RawTarget()
        msg.capture_stamp = sample.capture_stamp
        msg.task_id = self._task_id
        msg.sequence_id = self._sequence_id
        msg.target_x = prediction.target_x
        msg.target_y = prediction.target_y
        msg.predicted_t_remain = seconds_to_duration(prediction.predicted_t_remain)
        msg.sigma_x = prediction.sigma_x
        msg.sigma_y = prediction.sigma_y
        self._target_publisher.publish(msg)
        self._runtime_logger.record_target(msg)
        self._sequence_id = (self._sequence_id + 1) & 0xFFFFFFFF

    def _complete_single_task_if_gap(self, now_ns: int) -> bool:
        if (
            not self._single_task_mode
            or self._single_task_complete
            or self._last_observation_ns is None
            or now_ns - self._last_observation_ns <= self._new_task_gap_ns
        ):
            return False
        self._complete_single_task("observation_gap", now_ns)
        return True

    def _complete_single_task(self, reason: str, stamp_ns: int) -> None:
        if self._single_task_complete:
            return
        self._single_task_complete = True
        self._runtime_logger.record_event(
            "single_task_complete",
            {
                "reason": reason,
                "stamp_ns": int(stamp_ns),
                "task_id": int(self._task_id),
                "last_sequence_id": int((self._sequence_id - 1) & 0xFFFFFFFF),
            },
        )
        self.get_logger().info(f"single task {self._task_id} complete: {reason}")
        if self._single_task_shutdown_on_complete and rclpy.ok():
            rclpy.shutdown()

    def _closest_pose_with_delta(
        self,
        stamp_ns: int,
    ) -> tuple[PoseSample | None, PoseSample | None, int | None]:
        if not self._pose_buffer:
            return None, None, None
        closest = min(self._pose_buffer, key=lambda pose: abs(pose.stamp_ns - stamp_ns))
        delta_ns = closest.stamp_ns - stamp_ns
        if abs(delta_ns) > self._max_pose_age_ns:
            return None, closest, delta_ns
        return closest, closest, delta_ns

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

    def close(self) -> None:
        self._runtime_logger.close()


class StereoSample:
    def __init__(
        self,
        *,
        frame_id: int,
        capture_stamp: Time,
        capture_ns: int,
        point_camera_m: tuple[float, float, float],
        confidence: float,
    ) -> None:
        self.frame_id = frame_id
        self.capture_stamp = capture_stamp
        self.capture_ns = capture_ns
        self.point_camera_m = point_camera_m
        self.confidence = confidence


def duration_to_nanoseconds(duration: Any) -> int:
    return int(duration.sec) * NANOSECONDS_PER_SECOND + int(duration.nanosec)


def time_to_nanoseconds(stamp: Time) -> int:
    return int(stamp.sec) * NANOSECONDS_PER_SECOND + int(stamp.nanosec)


def stamp_to_dict(stamp: Time) -> dict[str, int]:
    sec = int(stamp.sec)
    nanosec = int(stamp.nanosec)
    return {
        "sec": sec,
        "nanosec": nanosec,
        "ns": sec * NANOSECONDS_PER_SECOND + nanosec,
    }


def pose_to_dict(pose: PoseSample) -> dict[str, float | int]:
    return {
        "stamp_ns": int(pose.stamp_ns),
        "x": float(pose.x),
        "y": float(pose.y),
        "z": float(pose.z),
        "roll": float(pose.roll),
        "pitch": float(pose.pitch),
        "yaw": float(pose.yaw),
    }


def frame_shape(frame: Any) -> list[int]:
    return [int(value) for value in frame.shape]


def detection_to_dict(detection: Any) -> dict[str, float | int]:
    return {
        "x1": float(detection.x1),
        "y1": float(detection.y1),
        "x2": float(detection.x2),
        "y2": float(detection.y2),
        "center_x": float(detection.x),
        "center_y": float(detection.y),
        "width": float(detection.width),
        "height": float(detection.height),
        "confidence": float(detection.confidence),
        "class_id": int(detection.class_id),
    }


def match_to_dict(match: Any) -> dict[str, Any]:
    return {
        "left_detection": detection_to_dict(match.left_detection),
        "right_detection": detection_to_dict(match.right_detection),
        "left_rectified": [float(value) for value in match.left_rectified],
        "right_rectified": [float(value) for value in match.right_rectified],
        "point_3d_m": [float(value) for value in match.point_3d_m.tolist()],
        "disparity_px": float(match.disparity_px),
        "epipolar_error_px": float(match.epipolar_error_px),
        "reprojection_error_px": float(match.reprojection_error_px),
        "confidence": float(match.confidence),
        "cost": float(match.cost),
    }


def diagnostics_to_dict(diagnostics: Any) -> dict[str, Any]:
    return {
        "evaluated_candidate_count": int(diagnostics.evaluated_candidate_count),
        "rejected_by_epipolar_count": int(diagnostics.rejected_by_epipolar_count),
        "rejected_by_disparity_count": int(diagnostics.rejected_by_disparity_count),
        "rejected_by_triangulation_count": int(diagnostics.rejected_by_triangulation_count),
        "rejected_by_depth_count": int(diagnostics.rejected_by_depth_count),
        "best_cost": None if diagnostics.best_cost is None else float(diagnostics.best_cost),
        "candidates": list(getattr(diagnostics, "candidates", [])),
    }


class RuntimeRunLogger:
    def __init__(
        self,
        *,
        enabled: bool,
        session_dir: Path | None,
        video_enabled: bool,
        chassis_enabled: bool,
        yolo_enabled: bool,
        targets_enabled: bool,
        events_enabled: bool,
        video_fourcc: str,
        video_fps: float,
        metadata: dict[str, Any],
    ) -> None:
        self.enabled = enabled
        self.session_dir = session_dir
        self.video_enabled = video_enabled
        self.chassis_enabled = chassis_enabled
        self.yolo_enabled = yolo_enabled
        self.targets_enabled = targets_enabled
        self.events_enabled = events_enabled
        self.video_fourcc = video_fourcc
        self.video_fps = video_fps
        self._frame_id = 0
        self._files: dict[str, TextIO] = {}
        self._left_writer: Any | None = None
        self._right_writer: Any | None = None
        self._video_initialized = False

        if not enabled or session_dir is None:
            return
        session_dir.mkdir(parents=True, exist_ok=False)
        (session_dir / "session.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        if chassis_enabled:
            self._files["chassis"] = self._open_ndjson("chassis.ndjson")
        if yolo_enabled or video_enabled:
            self._files["frames"] = self._open_ndjson("frames.ndjson")
        if yolo_enabled:
            self._files["detections"] = self._open_ndjson("detections.ndjson")
            self._files["observations"] = self._open_ndjson("observations.ndjson")
        if targets_enabled:
            self._files["targets"] = self._open_ndjson("targets.ndjson")
        if events_enabled:
            self._files["events"] = self._open_ndjson("events.ndjson")

    @classmethod
    def from_node(cls, node: VisionRuntimeNode) -> RuntimeRunLogger:
        enabled = bool(node.get_parameter("runtime_log_enabled").value)
        root = Path(str(node.get_parameter("runtime_log_root").value)).expanduser()
        session = str(node.get_parameter("runtime_log_session").value).strip()
        if not session:
            session = "vision_runtime_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        video_fourcc = str(node.get_parameter("runtime_log_video_fourcc").value)
        if len(video_fourcc) != 4:
            raise ValueError("runtime_log_video_fourcc must contain exactly four characters")

        metadata = {
            "schema_version": "tennisbot.vision_runtime_log.v1",
            "created_at_local": datetime.now().isoformat(timespec="seconds"),
            "node": "vision_runtime",
            "topics": {
                "chassis_position": str(node.get_parameter("chassis_position_topic").value),
                "raw_target": str(node.get_parameter("raw_target_topic").value),
            },
            "runtime": {
                "left_device": str(node.get_parameter("left_device").value),
                "right_device": str(node.get_parameter("right_device").value),
                "width": int(node.get_parameter("width").value),
                "height": int(node.get_parameter("height").value),
                "fps": float(node.get_parameter("fps").value),
                "fourcc": str(node.get_parameter("fourcc").value),
                "model_path": str(node.get_parameter("model_path").value),
                "calibration_package": str(node.get_parameter("calibration_package").value),
                "tile": bool(node.get_parameter("tile").value),
                "chassis_position_frame": "field",
                "initial_task_id": int(node.get_parameter("initial_task_id").value),
                "single_task_mode": bool(node.get_parameter("single_task_mode").value),
            },
            "files": {
                "left_video": "left.mp4",
                "right_video": "right.mp4",
                "frames": "frames.ndjson",
                "chassis": "chassis.ndjson",
                "detections": "detections.ndjson",
                "observations": "observations.ndjson",
                "targets": "targets.ndjson",
                "events": "events.ndjson",
            },
        }
        session_dir = root / session if enabled else None
        return cls(
            enabled=enabled,
            session_dir=session_dir,
            video_enabled=bool(node.get_parameter("runtime_log_video").value),
            chassis_enabled=bool(node.get_parameter("runtime_log_chassis").value),
            yolo_enabled=bool(node.get_parameter("runtime_log_yolo").value),
            targets_enabled=bool(node.get_parameter("runtime_log_targets").value),
            events_enabled=bool(node.get_parameter("runtime_log_events").value),
            video_fourcc=video_fourcc,
            video_fps=float(node.get_parameter("fps").value),
            metadata=metadata,
        )

    def _open_ndjson(self, name: str) -> TextIO:
        if self.session_dir is None:
            raise RuntimeError("runtime log session directory is not available")
        return (self.session_dir / name).open("a", encoding="utf-8", buffering=1)

    def record_frame(
        self,
        *,
        cv2_module: Any,
        capture_stamp: Time,
        left_frame: Any,
        right_frame: Any,
    ) -> int:
        frame_id = self._frame_id
        self._frame_id += 1
        if not self.enabled:
            return frame_id

        if self.video_enabled:
            self._ensure_video_writers(cv2_module, left_frame)
            if self._left_writer is not None:
                self._left_writer.write(left_frame)
            if self._right_writer is not None:
                self._right_writer.write(right_frame)

        self._write(
            "frames",
            {
                "frame_id": frame_id,
                "capture_stamp": stamp_to_dict(capture_stamp),
                "left_shape": frame_shape(left_frame),
                "right_shape": frame_shape(right_frame),
            },
        )
        return frame_id

    def _ensure_video_writers(self, cv2_module: Any, frame: Any) -> None:
        if self._video_initialized:
            return
        self._video_initialized = True
        if self.session_dir is None:
            return
        height, width = frame.shape[:2]
        fourcc = cv2_module.VideoWriter_fourcc(*self.video_fourcc)
        left = cv2_module.VideoWriter(
            str(self.session_dir / "left.mp4"),
            fourcc,
            self.video_fps,
            (int(width), int(height)),
        )
        right = cv2_module.VideoWriter(
            str(self.session_dir / "right.mp4"),
            fourcc,
            self.video_fps,
            (int(width), int(height)),
        )
        if left.isOpened() and right.isOpened():
            self._left_writer = left
            self._right_writer = right
            return
        left.release()
        right.release()
        self.video_enabled = False
        self.record_event("video_writer_disabled", {"reason": "VideoWriter failed to open"})

    def record_chassis(
        self,
        *,
        stamp: Time,
        source: dict[str, float | int],
        pose: PoseSample,
    ) -> None:
        self._write(
            "chassis",
            {
                "stamp": stamp_to_dict(stamp),
                "source": source,
                "frame": "field",
                "field_pose": pose_to_dict(pose),
            },
        )

    def record_yolo(
        self,
        *,
        frame_id: int,
        capture_stamp: Time,
        left_detections: list[Any],
        right_detections: list[Any],
        match: Any | None,
        diagnostics: Any,
    ) -> None:
        self._write(
            "detections",
            {
                "frame_id": frame_id,
                "capture_stamp": stamp_to_dict(capture_stamp),
                "left": [detection_to_dict(item) for item in left_detections],
                "right": [detection_to_dict(item) for item in right_detections],
                "selected_match": None if match is None else match_to_dict(match),
                "diagnostics": diagnostics_to_dict(diagnostics),
            },
        )

    def record_observation(
        self,
        *,
        frame_id: int,
        capture_stamp: Time,
        point_camera_m: tuple[float, float, float],
        field_point: Any,
        confidence: float,
    ) -> None:
        self._write(
            "observations",
            {
                "frame_id": frame_id,
                "capture_stamp": stamp_to_dict(capture_stamp),
                "point_camera_m": [float(value) for value in point_camera_m],
                "point_field_m": {
                    "x": float(field_point.x),
                    "y": float(field_point.y),
                    "z": float(field_point.z),
                },
                "confidence": float(confidence),
            },
        )

    def record_target(self, msg: RawTarget) -> None:
        self._write(
            "targets",
            {
                "capture_stamp": stamp_to_dict(msg.capture_stamp),
                "task_id": int(msg.task_id),
                "sequence_id": int(msg.sequence_id),
                "target_x": float(msg.target_x),
                "target_y": float(msg.target_y),
                "predicted_t_remain_ns": duration_to_nanoseconds(msg.predicted_t_remain),
                "sigma_x": float(msg.sigma_x),
                "sigma_y": float(msg.sigma_y),
            },
        )

    def record_event(self, event: str, payload: dict[str, Any]) -> None:
        self._write(
            "events",
            {
                "event": event,
                "payload": payload,
            },
        )

    def _write(self, stream: str, value: dict[str, Any]) -> None:
        if not self.enabled:
            return
        file = self._files.get(stream)
        if file is None:
            return
        file.write(json.dumps(value, sort_keys=True) + "\n")

    def close(self) -> None:
        if self._left_writer is not None:
            self._left_writer.release()
        if self._right_writer is not None:
            self._right_writer.release()
        for file in self._files.values():
            file.close()
        self._files.clear()


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
        logger: RuntimeRunLogger,
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
        self.logger = logger
        self.calibration_package = calibration_package
        self.width = width
        self.height = height

    @classmethod
    def from_node(cls, node: VisionRuntimeNode) -> CameraRuntime:
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
            logger=node._runtime_logger,
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

        frame_id = self.logger.record_frame(
            cv2_module=self.cv2,
            capture_stamp=capture_time.to_msg(),
            left_frame=left_frame,
            right_frame=right_frame,
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
        self.logger.record_yolo(
            frame_id=frame_id,
            capture_stamp=capture_time.to_msg(),
            left_detections=left_detections,
            right_detections=right_detections,
            match=match,
            diagnostics=self.matcher.last_diagnostics,
        )
        if match is None:
            raise RuntimeError("no valid stereo ball match")
        point = match.point_3d_m
        return StereoSample(
            frame_id=frame_id,
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
    node = VisionRuntimeNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, RCLError):
        pass
    finally:
        if node._runtime is not None:
            node._runtime.left_capture.release()
            node._runtime.right_capture.release()
        node.close()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
