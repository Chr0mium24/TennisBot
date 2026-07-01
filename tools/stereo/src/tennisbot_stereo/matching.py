from __future__ import annotations

import numpy as np

from .calibration import RuntimeStereoCalibration
from .types import BallDetection, StereoBallMatch, StereoMatchDiagnostics


class StereoBallMatcher:
    def __init__(
        self,
        calibration: RuntimeStereoCalibration,
        *,
        max_epipolar_error_px: float,
        min_disparity_px: float,
        max_disparity_px: float,
        max_depth_m: float,
        reprojection_weight: float = 0.25,
        temporal_weight: float = 0.02,
    ) -> None:
        self.calibration = calibration
        self.max_epipolar_error_px = max_epipolar_error_px
        self.min_disparity_px = min_disparity_px
        self.max_disparity_px = max_disparity_px
        self.max_depth_m = max_depth_m
        self.reprojection_weight = reprojection_weight
        self.temporal_weight = temporal_weight
        self.previous_point: np.ndarray | None = None
        self.last_diagnostics = StereoMatchDiagnostics()

    def select(self, left_detections: list[BallDetection], right_detections: list[BallDetection]) -> StereoBallMatch | None:
        best_match: StereoBallMatch | None = None
        best_cost = float("inf")
        evaluated = 0
        rejected_epipolar = 0
        rejected_disparity = 0
        rejected_triangulation = 0
        rejected_depth = 0

        for left in left_detections:
            left_rectified = self.calibration.rectified_left_point((left.x, left.y))
            for right in right_detections:
                evaluated += 1
                right_rectified = self.calibration.rectified_right_point((right.x, right.y))
                epipolar_error = abs(left_rectified[1] - right_rectified[1])
                if epipolar_error > self.max_epipolar_error_px:
                    rejected_epipolar += 1
                    continue

                disparity = self.calibration.disparity_sign * (left_rectified[0] - right_rectified[0])
                if disparity < self.min_disparity_px or disparity > self.max_disparity_px:
                    rejected_disparity += 1
                    continue

                try:
                    point_3d = self.calibration.triangulate_rectified(left_rectified, right_rectified)
                    reprojection_error = self.calibration.reprojection_error_rectified(
                        point_3d,
                        left_rectified,
                        right_rectified,
                    )
                except ValueError:
                    rejected_triangulation += 1
                    continue

                z_m = float(point_3d[2])
                if z_m <= 0.0 or z_m > self.max_depth_m:
                    rejected_depth += 1
                    continue

                confidence = min(left.confidence, right.confidence)
                cost = epipolar_error + self.reprojection_weight * reprojection_error - confidence
                if self.previous_point is not None:
                    cost += self.temporal_weight * float(np.linalg.norm(point_3d - self.previous_point))
                if cost >= best_cost:
                    continue

                best_cost = cost
                best_match = StereoBallMatch(
                    left_detection=left,
                    right_detection=right,
                    left_rectified=left_rectified,
                    right_rectified=right_rectified,
                    point_3d_m=point_3d,
                    disparity_px=float(disparity),
                    epipolar_error_px=float(epipolar_error),
                    reprojection_error_px=float(reprojection_error),
                    confidence=float(confidence),
                    cost=float(cost),
                )

        self.previous_point = None if best_match is None else best_match.point_3d_m
        self.last_diagnostics = StereoMatchDiagnostics(
            evaluated_candidate_count=evaluated,
            rejected_by_epipolar_count=rejected_epipolar,
            rejected_by_disparity_count=rejected_disparity,
            rejected_by_triangulation_count=rejected_triangulation,
            rejected_by_depth_count=rejected_depth,
            best_cost=None if not np.isfinite(best_cost) else float(best_cost),
        )
        return best_match
