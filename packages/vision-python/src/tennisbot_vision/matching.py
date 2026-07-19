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
        candidates: list[dict[str, object]] = []
        best_candidate: dict[str, object] | None = None

        for left_index, left in enumerate(left_detections):
            left_rectified = self.calibration.rectified_left_point((left.x, left.y))
            for right_index, right in enumerate(right_detections):
                evaluated += 1
                right_rectified = self.calibration.rectified_right_point((right.x, right.y))
                epipolar_error = abs(left_rectified[1] - right_rectified[1])
                disparity = self.calibration.disparity_sign * (left_rectified[0] - right_rectified[0])
                candidate: dict[str, object] = {
                    "left_index": left_index,
                    "right_index": right_index,
                    "left_center_px": [float(left.x), float(left.y)],
                    "right_center_px": [float(right.x), float(right.y)],
                    "left_rectified_px": [float(left_rectified[0]), float(left_rectified[1])],
                    "right_rectified_px": [float(right_rectified[0]), float(right_rectified[1])],
                    "epipolar_error_px": float(epipolar_error),
                    "disparity_px": float(disparity),
                    "left_confidence": float(left.confidence),
                    "right_confidence": float(right.confidence),
                    "confidence": float(min(left.confidence, right.confidence)),
                    "selected": False,
                }
                if epipolar_error > self.max_epipolar_error_px:
                    rejected_epipolar += 1
                    candidate["rejected_by"] = "epipolar"
                    candidates.append(candidate)
                    continue

                if disparity < self.min_disparity_px or disparity > self.max_disparity_px:
                    rejected_disparity += 1
                    candidate["rejected_by"] = "disparity"
                    candidates.append(candidate)
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
                    candidate["rejected_by"] = "triangulation"
                    candidates.append(candidate)
                    continue

                z_m = float(point_3d[2])
                candidate["point_3d_m"] = [float(value) for value in point_3d.tolist()]
                candidate["reprojection_error_px"] = float(reprojection_error)
                candidate["depth_m"] = z_m
                if z_m <= 0.0 or z_m > self.max_depth_m:
                    rejected_depth += 1
                    candidate["rejected_by"] = "depth"
                    candidates.append(candidate)
                    continue

                confidence = min(left.confidence, right.confidence)
                cost = epipolar_error + self.reprojection_weight * reprojection_error - confidence
                if self.previous_point is not None:
                    cost += self.temporal_weight * float(np.linalg.norm(point_3d - self.previous_point))
                candidate["cost"] = float(cost)
                if cost >= best_cost:
                    candidate["rejected_by"] = "higher_cost"
                    candidates.append(candidate)
                    continue

                if best_candidate is not None:
                    best_candidate["rejected_by"] = "higher_cost"
                best_cost = cost
                candidate["rejected_by"] = None
                candidates.append(candidate)
                best_candidate = candidate
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
        if best_candidate is not None:
            best_candidate["selected"] = True
        self.last_diagnostics = StereoMatchDiagnostics(
            evaluated_candidate_count=evaluated,
            rejected_by_epipolar_count=rejected_epipolar,
            rejected_by_disparity_count=rejected_disparity,
            rejected_by_triangulation_count=rejected_triangulation,
            rejected_by_depth_count=rejected_depth,
            best_cost=None if not np.isfinite(best_cost) else float(best_cost),
            candidates=candidates,
        )
        return best_match
