from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PoseSample:
    stamp_ns: int
    x: float
    y: float
    z: float
    roll: float
    pitch: float
    yaw: float


@dataclass(frozen=True)
class Transform3D:
    translation_m: tuple[float, float, float]
    rotation_rpy_rad: tuple[float, float, float]


@dataclass(frozen=True)
class FieldPoint:
    x: float
    y: float
    z: float


def camera_point_to_field(
    camera_point_m: tuple[float, float, float],
    *,
    chassis_pose: PoseSample,
    chassis_from_camera: Transform3D,
) -> FieldPoint:
    chassis_point = apply_transform(camera_point_m, chassis_from_camera)
    field_point = transform_chassis_point_to_field(chassis_point, chassis_pose)
    return FieldPoint(*field_point)


def apply_transform(
    point: tuple[float, float, float],
    transform: Transform3D,
) -> tuple[float, float, float]:
    rotated = mat_vec_mul(rpy_matrix(*transform.rotation_rpy_rad), point)
    return (
        rotated[0] + transform.translation_m[0],
        rotated[1] + transform.translation_m[1],
        rotated[2] + transform.translation_m[2],
    )


def transform_chassis_point_to_field(
    chassis_point: tuple[float, float, float],
    pose: PoseSample,
) -> tuple[float, float, float]:
    yaw_rotation = rpy_matrix(0.0, 0.0, pose.yaw)
    rotated = mat_vec_mul(yaw_rotation, chassis_point)
    return (
        pose.x + rotated[0],
        pose.y + rotated[1],
        pose.z + rotated[2],
    )


def cartesian_pose_to_field(
    x: float,
    y: float,
    z: float,
    roll: float,
    pitch: float,
    yaw: float,
) -> tuple[float, float, float, float, float, float]:
    return (
        y,
        -x,
        z,
        roll,
        pitch,
        normalize_angle(yaw - math.pi / 2.0),
    )


def rpy_matrix(roll: float, pitch: float, yaw: float) -> tuple[tuple[float, float, float], ...]:
    cr = math.cos(roll)
    sr = math.sin(roll)
    cp = math.cos(pitch)
    sp = math.sin(pitch)
    cy = math.cos(yaw)
    sy = math.sin(yaw)

    return (
        (cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr),
        (sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr),
        (-sp, cp * sr, cp * cr),
    )


def mat_vec_mul(
    matrix: tuple[tuple[float, float, float], ...],
    vector: tuple[float, float, float],
) -> tuple[float, float, float]:
    return (
        matrix[0][0] * vector[0] + matrix[0][1] * vector[1] + matrix[0][2] * vector[2],
        matrix[1][0] * vector[0] + matrix[1][1] * vector[1] + matrix[1][2] * vector[2],
        matrix[2][0] * vector[0] + matrix[2][1] * vector[1] + matrix[2][2] * vector[2],
    )


def normalize_angle(angle_rad: float) -> float:
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi
