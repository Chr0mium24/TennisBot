from __future__ import annotations

import math
import unittest

from tennisbot_headless_vision.geometry import (
    PoseSample,
    Transform3D,
    apply_transform,
    camera_point_to_field,
    mat_vec_mul,
    rpy_matrix,
)
from tennisbot_headless_vision.trajectory import BallObservation, TrajectoryPrediction, predict_target


class CoordinateFrameParityTest(unittest.TestCase):
    def test_field_algorithm_matches_legacy_cartesian_algorithm_after_frame_conversion(self) -> None:
        chassis_from_camera = Transform3D(
            translation_m=(0.12, -0.03, 0.64),
            rotation_rpy_rad=(-math.pi / 2.0, 0.04, -math.pi / 2.0),
        )
        cartesian_poses = [
            cartesian_pose(1710000000000000000, x=-1.2, y=2.5, yaw=0.72),
            cartesian_pose(1710000000050000000, x=-1.1, y=2.6, yaw=0.74),
            cartesian_pose(1710000000100000000, x=-1.0, y=2.7, yaw=0.76),
            cartesian_pose(1710000000150000000, x=-0.9, y=2.8, yaw=0.78),
            cartesian_pose(1710000000200000000, x=-0.8, y=2.9, yaw=0.80),
            cartesian_pose(1710000000250000000, x=-0.7, y=3.0, yaw=0.82),
        ]
        camera_points = [
            (0.06, -0.48, 2.20),
            (0.08, -0.56, 2.35),
            (0.11, -0.61, 2.52),
            (0.15, -0.63, 2.70),
            (0.20, -0.61, 2.90),
            (0.26, -0.56, 3.12),
        ]

        field_observations: list[BallObservation] = []
        legacy_cartesian_observations: list[BallObservation] = []
        for cartesian_chassis_pose, camera_point in zip(
            cartesian_poses,
            camera_points,
            strict=True,
        ):
            field_pose = field_pose_from_legacy_cartesian(cartesian_chassis_pose)
            direct_field_point = camera_point_to_field(
                camera_point,
                chassis_pose=field_pose,
                chassis_from_camera=chassis_from_camera,
            )
            legacy_cartesian_point = camera_point_to_legacy_cartesian(
                camera_point,
                chassis_pose=cartesian_chassis_pose,
                chassis_from_camera=chassis_from_camera,
            )

            self.assertAlmostEqual(direct_field_point.x, legacy_cartesian_point[1])
            self.assertAlmostEqual(direct_field_point.y, -legacy_cartesian_point[0])
            self.assertAlmostEqual(direct_field_point.z, legacy_cartesian_point[2])

            field_observations.append(
                BallObservation(
                    stamp_ns=cartesian_chassis_pose.stamp_ns,
                    x=direct_field_point.x,
                    y=direct_field_point.y,
                    z=direct_field_point.z,
                    confidence=1.0,
                )
            )
            legacy_cartesian_observations.append(
                BallObservation(
                    stamp_ns=cartesian_chassis_pose.stamp_ns,
                    x=legacy_cartesian_point[0],
                    y=legacy_cartesian_point[1],
                    z=legacy_cartesian_point[2],
                    confidence=1.0,
                )
            )

        field_prediction = predict(field_observations)
        legacy_cartesian_prediction = predict(legacy_cartesian_observations)

        self.assertAlmostEqual(field_prediction.target_x, legacy_cartesian_prediction.target_y)
        self.assertAlmostEqual(field_prediction.target_y, -legacy_cartesian_prediction.target_x)
        self.assertAlmostEqual(field_prediction.target_z, legacy_cartesian_prediction.target_z)
        self.assertAlmostEqual(
            field_prediction.predicted_t_remain,
            legacy_cartesian_prediction.predicted_t_remain,
        )
        self.assertAlmostEqual(field_prediction.sigma_x, legacy_cartesian_prediction.sigma_y)
        self.assertAlmostEqual(field_prediction.sigma_y, legacy_cartesian_prediction.sigma_x)


def cartesian_pose(stamp_ns: int, *, x: float, y: float, yaw: float) -> PoseSample:
    return PoseSample(
        stamp_ns=stamp_ns,
        x=x,
        y=y,
        z=0.0,
        roll=0.0,
        pitch=0.0,
        yaw=yaw,
    )


def field_pose_from_legacy_cartesian(pose: PoseSample) -> PoseSample:
    return PoseSample(
        stamp_ns=pose.stamp_ns,
        x=pose.y,
        y=-pose.x,
        z=pose.z,
        roll=pose.roll,
        pitch=pose.pitch,
        yaw=pose.yaw - math.pi / 2.0,
    )


def camera_point_to_legacy_cartesian(
    camera_point_m: tuple[float, float, float],
    *,
    chassis_pose: PoseSample,
    chassis_from_camera: Transform3D,
) -> tuple[float, float, float]:
    chassis_point = apply_transform(camera_point_m, chassis_from_camera)
    rotated = mat_vec_mul(rpy_matrix(0.0, 0.0, chassis_pose.yaw), chassis_point)
    return (
        chassis_pose.x + rotated[0],
        chassis_pose.y + rotated[1],
        chassis_pose.z + rotated[2],
    )


def predict(observations: list[BallObservation]) -> TrajectoryPrediction:
    prediction = predict_target(
        observations,
        target_plane_z=0.6,
        gravity_mps2=9.80665,
        min_time_s=0.000001,
        max_time_s=5.0,
        min_sigma_m=0.001,
        method="weighted-ls",
    )
    if prediction is None:
        raise AssertionError("expected a target prediction")
    return prediction


if __name__ == "__main__":
    unittest.main()
