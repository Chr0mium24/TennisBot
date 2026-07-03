from __future__ import annotations

import unittest

from tennisbot_vision_runtime.trajectory import BallObservation, predict_target


class TrajectoryParityTest(unittest.TestCase):
    def test_two_frame_prediction_matches_ts_reference(self) -> None:
        prediction = predict_target(
            [
                observation(1710000000000, x=0.0, y=0.0, z=1.0),
                observation(1710000001000, x=2.0, y=1.0, z=4.0),
            ],
            target_plane_z=0.0,
            gravity_mps2=9.81,
            min_time_s=0.000001,
            max_time_s=5.0,
            min_sigma_m=0.05,
        )

        self.assertIsNotNone(prediction)
        assert prediction is not None
        self.assertEqual(prediction.model, "projectile-3d-two-frame-constant-gravity")
        self.assertEqual(prediction.source_count, 2)
        self.assertAlmostEqual(prediction.predicted_t_remain, 1.2592328604354677)
        self.assertAlmostEqual(prediction.target_x, 4.518465720870935)
        self.assertAlmostEqual(prediction.target_y, 2.2592328604354677)
        self.assertEqual(prediction.target_z, 0.0)

    def test_weighted_ls_default_matches_ts_reference(self) -> None:
        prediction = predict_target(
            sample_trajectory(
                count=5,
                interval_ms=50,
                start_unix_ms=1710000000000,
                start=(0.1, 0.4, 1.2),
                velocity=(1.5, 4.0, 3.2),
            ),
            target_plane_z=0.0,
            gravity_mps2=9.81,
            min_time_s=0.000001,
            max_time_s=5.0,
            min_sigma_m=0.05,
        )

        self.assertIsNotNone(prediction)
        assert prediction is not None
        self.assertEqual(prediction.model, "projectile-3d-weighted-ls9-constant-gravity")
        self.assertEqual(prediction.source_count, 5)
        self.assertAlmostEqual(prediction.predicted_t_remain, 0.7186952636884203)
        self.assertAlmostEqual(prediction.target_x, 1.47804289553263)
        self.assertAlmostEqual(prediction.target_y, 4.07478105475368)

    def test_ransac_default_matches_ts_outlier_reference(self) -> None:
        clean = sample_trajectory(
            count=10,
            interval_ms=50,
            start_unix_ms=1710000000000,
            start=(-0.2, 0.3, 1.1),
            velocity=(1.1, 5.2, 3.6),
        )
        with_outlier = [
            replace_observation(item, dx=2.5, dy=-3.0, dz=1.8) if index == 8 else item
            for index, item in enumerate(clean)
        ]

        robust = predict_target(
            with_outlier,
            target_plane_z=0.0,
            gravity_mps2=9.81,
            min_time_s=0.000001,
            max_time_s=5.0,
            min_sigma_m=0.05,
        )
        polluted_weighted = predict_target(
            with_outlier,
            target_plane_z=0.0,
            gravity_mps2=9.81,
            min_time_s=0.000001,
            max_time_s=5.0,
            min_sigma_m=0.05,
            method="weighted-ls",
        )

        self.assertIsNotNone(robust)
        self.assertIsNotNone(polluted_weighted)
        assert robust is not None
        assert polluted_weighted is not None
        self.assertEqual(robust.model, "projectile-3d-weighted-ls9-ransac-constant-gravity")
        self.assertEqual(robust.source_count, 9)
        self.assertEqual(robust.inlier_count, 9)
        self.assertAlmostEqual(robust.predicted_t_remain, 0.5160799441588662)
        self.assertAlmostEqual(robust.target_x, 0.862687938574753)
        self.assertAlmostEqual(robust.target_y, 5.323615709626105)
        self.assertGreater(abs(polluted_weighted.target_x - robust.target_x), 0.2)

    def test_unreachable_target_plane_returns_no_ros_target(self) -> None:
        prediction = predict_target(
            [
                observation(1710000000000, x=0.0, y=0.0, z=1.0),
                observation(1710000001000, x=1.0, y=1.0, z=1.0),
            ],
            target_plane_z=10.0,
            gravity_mps2=9.81,
            min_time_s=0.000001,
            max_time_s=5.0,
            min_sigma_m=0.05,
        )

        self.assertIsNone(prediction)


def observation(timestamp_unix_ms: int, *, x: float, y: float, z: float) -> BallObservation:
    return BallObservation(
        stamp_ns=timestamp_unix_ms * 1_000_000,
        x=x,
        y=y,
        z=z,
        confidence=1.0,
    )


def replace_observation(
    item: BallObservation,
    *,
    dx: float,
    dy: float,
    dz: float,
) -> BallObservation:
    return BallObservation(
        stamp_ns=item.stamp_ns,
        x=item.x + dx,
        y=item.y + dy,
        z=item.z + dz,
        confidence=item.confidence,
    )


def sample_trajectory(
    *,
    count: int,
    interval_ms: int,
    start_unix_ms: int,
    start: tuple[float, float, float],
    velocity: tuple[float, float, float],
) -> list[BallObservation]:
    points: list[BallObservation] = []
    for index in range(count):
        t_s = (interval_ms * index) / 1000
        points.append(
            observation(
                start_unix_ms + interval_ms * index,
                x=start[0] + velocity[0] * t_s,
                y=start[1] + velocity[1] * t_s,
                z=start[2] + velocity[2] * t_s - 0.5 * 9.81 * t_s * t_s,
            )
        )
    return points


if __name__ == "__main__":
    unittest.main()
