from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np


ImageSize = tuple[int, int]


@dataclass(frozen=True)
class RuntimeStereoCalibration:
    image_size: ImageSize
    left_camera_id: str
    right_camera_id: str
    camera_matrix_left: np.ndarray
    dist_coeffs_left: np.ndarray
    camera_matrix_right: np.ndarray
    dist_coeffs_right: np.ndarray
    rectify_left: np.ndarray
    rectify_right: np.ndarray
    projection_left: np.ndarray
    projection_right: np.ndarray
    baseline_m: float | None
    source_image_size: ImageSize
    package_dir: Path

    @classmethod
    def from_package(
        cls,
        package_dir: Path,
        *,
        frame_size: ImageSize | None = None,
    ) -> RuntimeStereoCalibration:
        package_dir = package_dir.resolve()
        package_json = _read_json(package_dir / "package.json")
        files = _files(package_json)
        cam1 = _read_json(package_dir / files.get("cam1", "cam1.json"))
        cam2 = _read_json(package_dir / files.get("cam2", "cam2.json"))
        stereo = _read_json(package_dir / files.get("stereo", "stereo.json"))
        rectification = _read_json(package_dir / files.get("rectification", "rectification.json"))

        source_size = _read_image_size(rectification)
        target_size = frame_size or source_size
        left_source_size = _read_image_size(cam1)
        right_source_size = _read_image_size(cam2)
        if left_source_size != source_size or right_source_size != source_size:
            raise ValueError("camera image_size must match rectification image_size")

        left_camera_id = str(cam1["camera_id"])
        right_camera_id = str(cam2["camera_id"])
        if rectification.get("left_camera_id") != left_camera_id:
            raise ValueError("rectification left_camera_id does not match cam1.json")
        if rectification.get("right_camera_id") != right_camera_id:
            raise ValueError("rectification right_camera_id does not match cam2.json")

        return cls(
            image_size=target_size,
            left_camera_id=left_camera_id,
            right_camera_id=right_camera_id,
            camera_matrix_left=_scale_camera_matrix(_array(cam1["camera_matrix"]), source_size, target_size),
            dist_coeffs_left=_array(cam1["distortion_coefficients"]).reshape(-1, 1),
            camera_matrix_right=_scale_camera_matrix(_array(cam2["camera_matrix"]), source_size, target_size),
            dist_coeffs_right=_array(cam2["distortion_coefficients"]).reshape(-1, 1),
            rectify_left=_array(rectification["r1"]),
            rectify_right=_array(rectification["r2"]),
            projection_left=_scale_projection(_array(rectification["p1"]), source_size, target_size),
            projection_right=_scale_projection(_array(rectification["p2"]), source_size, target_size),
            baseline_m=_optional_float(stereo.get("baseline_m")),
            source_image_size=source_size,
            package_dir=package_dir,
        )

    @property
    def disparity_sign(self) -> float:
        return -1.0 if float(self.projection_right[0, 3]) > 0.0 else 1.0

    def rectified_left_point(self, xy: tuple[float, float]) -> tuple[float, float]:
        return _rectify_point(
            xy,
            self.camera_matrix_left,
            self.dist_coeffs_left,
            self.rectify_left,
            self.projection_left,
        )

    def rectified_right_point(self, xy: tuple[float, float]) -> tuple[float, float]:
        return _rectify_point(
            xy,
            self.camera_matrix_right,
            self.dist_coeffs_right,
            self.rectify_right,
            self.projection_right,
        )

    def triangulate_rectified(
        self,
        left_xy: tuple[float, float],
        right_xy: tuple[float, float],
    ) -> np.ndarray:
        left_points = np.asarray(left_xy, dtype=np.float64).reshape(2, 1)
        right_points = np.asarray(right_xy, dtype=np.float64).reshape(2, 1)
        point_h = cv2.triangulatePoints(
            self.projection_left,
            self.projection_right,
            left_points,
            right_points,
        ).reshape(4)
        if abs(float(point_h[3])) < 1e-9:
            raise ValueError("triangulation returned an invalid homogeneous coordinate")
        point = point_h[:3] / point_h[3]
        if not np.all(np.isfinite(point)):
            raise ValueError("triangulation returned a non-finite point")
        return point

    def reprojection_error_rectified(
        self,
        point_3d: np.ndarray,
        left_xy: tuple[float, float],
        right_xy: tuple[float, float],
    ) -> float:
        left_reprojected = project_point(self.projection_left, point_3d)
        right_reprojected = project_point(self.projection_right, point_3d)
        left_error = math.hypot(left_reprojected[0] - left_xy[0], left_reprojected[1] - left_xy[1])
        right_error = math.hypot(right_reprojected[0] - right_xy[0], right_reprojected[1] - right_xy[1])
        return float((left_error + right_error) * 0.5)


def project_point(projection: np.ndarray, point_3d: np.ndarray) -> tuple[float, float]:
    point_h = np.append(point_3d.astype(np.float64), 1.0).reshape(4, 1)
    projected = projection @ point_h
    if abs(float(projected[2, 0])) < 1e-9:
        raise ValueError("point projects with zero homogeneous depth")
    return float(projected[0, 0] / projected[2, 0]), float(projected[1, 0] / projected[2, 0])


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _files(package_json: dict[str, Any]) -> dict[str, str]:
    value = package_json.get("files", {})
    if not isinstance(value, dict):
        raise ValueError("package.json files must be an object")
    return {str(key): str(path) for key, path in value.items()}


def _read_image_size(payload: dict[str, Any]) -> ImageSize:
    value = payload.get("image_size")
    if isinstance(value, dict):
        return int(value["width"]), int(value["height"])
    if isinstance(value, list | tuple) and len(value) == 2:
        return int(value[0]), int(value[1])
    raise ValueError("calibration payload is missing image_size")


def _array(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64)


def _scale_camera_matrix(matrix: np.ndarray, source_size: ImageSize, target_size: ImageSize) -> np.ndarray:
    scaled = matrix.astype(np.float64, copy=True)
    if source_size == target_size:
        return scaled
    sx, sy = _scale_factors(source_size, target_size)
    scaled[0, :] *= sx
    scaled[1, :] *= sy
    return scaled


def _scale_projection(projection: np.ndarray, source_size: ImageSize, target_size: ImageSize) -> np.ndarray:
    scaled = projection.astype(np.float64, copy=True)
    if source_size == target_size:
        return scaled
    sx, sy = _scale_factors(source_size, target_size)
    scaled[0, :] *= sx
    scaled[1, :] *= sy
    return scaled


def _scale_factors(source_size: ImageSize, target_size: ImageSize) -> tuple[float, float]:
    source_width, source_height = source_size
    target_width, target_height = target_size
    if source_width <= 0 or source_height <= 0 or target_width <= 0 or target_height <= 0:
        raise ValueError("image sizes must be positive")
    return target_width / source_width, target_height / source_height


def _rectify_point(
    xy: tuple[float, float],
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    rectify: np.ndarray,
    projection: np.ndarray,
) -> tuple[float, float]:
    point = np.asarray(xy, dtype=np.float64).reshape(1, 1, 2)
    rectified = cv2.undistortPoints(point, camera_matrix, dist_coeffs, R=rectify, P=projection).reshape(2)
    return float(rectified[0]), float(rectified[1])


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)
