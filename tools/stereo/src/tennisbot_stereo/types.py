from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class BallDetection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = 0

    @property
    def x(self) -> float:
        return 0.5 * (self.x1 + self.x2)

    @property
    def y(self) -> float:
        return 0.5 * (self.y1 + self.y2)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height


@dataclass(frozen=True)
class StereoBallMatch:
    left_detection: BallDetection
    right_detection: BallDetection
    left_rectified: tuple[float, float]
    right_rectified: tuple[float, float]
    point_3d_m: np.ndarray
    disparity_px: float
    epipolar_error_px: float
    reprojection_error_px: float
    confidence: float
    cost: float


@dataclass(frozen=True)
class StereoMatchDiagnostics:
    evaluated_candidate_count: int = 0
    rejected_by_epipolar_count: int = 0
    rejected_by_disparity_count: int = 0
    rejected_by_triangulation_count: int = 0
    rejected_by_depth_count: int = 0
    best_cost: float | None = None
