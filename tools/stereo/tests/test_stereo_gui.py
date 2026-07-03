from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tennisbot_stereo.calibration import RuntimeStereoCalibration, project_point
from tennisbot_stereo.matching import StereoBallMatcher
from tennisbot_stereo.types import BallDetection


def test_loads_and_scales_runtime_calibration_package(tmp_path: Path) -> None:
    package = write_calibration_package(tmp_path, image_size=(1920, 1080), p2_offset=120.0)

    calibration = RuntimeStereoCalibration.from_package(package, frame_size=(3840, 2160))

    assert calibration.image_size == (3840, 2160)
    assert calibration.source_image_size == (1920, 1080)
    assert calibration.camera_matrix_left[0, 0] == 2000
    assert calibration.camera_matrix_left[0, 2] == 1920
    assert calibration.projection_left[0, 0] == 2000
    assert calibration.projection_right[0, 3] == 240
    assert calibration.disparity_sign == -1.0


def test_matcher_uses_positive_p2_disparity_and_depth_filter(tmp_path: Path) -> None:
    package = write_calibration_package(tmp_path, image_size=(1280, 720), p2_offset=200.0)
    calibration = RuntimeStereoCalibration.from_package(package)
    matcher = StereoBallMatcher(
        calibration,
        max_epipolar_error_px=3,
        min_disparity_px=10,
        max_disparity_px=220,
        max_depth_m=3,
    )
    good_point = np.asarray([0.1, 0.04, 2.0], dtype=np.float64)
    far_point = np.asarray([0.1, 0.04, 10.0], dtype=np.float64)

    match = matcher.select(
        [
            detection_from_projection("left-far", calibration.projection_left, far_point, 0.99),
            detection_from_projection("left-good", calibration.projection_left, good_point, 0.7),
        ],
        [
            detection_from_projection("right-far", calibration.projection_right, far_point, 0.99),
            detection_from_projection("right-good", calibration.projection_right, good_point, 0.7),
        ],
    )

    assert match is not None
    assert match.left_detection.class_id == 0
    assert match.disparity_px == 100
    np.testing.assert_allclose(match.point_3d_m, good_point, atol=1e-9)
    assert matcher.last_diagnostics.rejected_by_depth_count > 0


def detection_from_projection(
    detection_id: str,
    projection: np.ndarray,
    point_3d: np.ndarray,
    confidence: float,
) -> BallDetection:
    x, y = project_point(projection, point_3d)
    return BallDetection(
        x1=x - 6,
        y1=y - 6,
        x2=x + 6,
        y2=y + 6,
        confidence=confidence,
        class_id=0 if detection_id else 1,
    )


def write_calibration_package(tmp_path: Path, *, image_size: tuple[int, int], p2_offset: float) -> Path:
    width, height = image_size
    package = tmp_path / "stereo_cam1_cam2"
    package.mkdir()
    write_json(
        package / "package.json",
        {
            "schema_version": "calibration.stereo.v1",
            "package_type": "stereo_camera_calibration",
            "camera_ids": ["cam1", "cam2"],
            "created_at": "2026-07-01T00:00:00Z",
            "source_session": "synthetic",
            "files": {
                "cam1": "cam1.json",
                "cam2": "cam2.json",
                "stereo": "stereo.json",
                "rectification": "rectification.json",
            },
            "quality": {"accepted": True},
        },
    )
    for camera_id in ("cam1", "cam2"):
        write_json(
            package / f"{camera_id}.json",
            {
                "schema_version": "calibration.camera_intrinsics.v1",
                "camera_id": camera_id,
                "image_size": {"width": width, "height": height},
                "camera_matrix": [
                    [1000, 0, width / 2],
                    [0, 1000, height / 2],
                    [0, 0, 1],
                ],
                "distortion_model": "none",
                "distortion_coefficients": [0, 0, 0, 0, 0],
            },
        )
    write_json(
        package / "stereo.json",
        {
            "schema_version": "calibration.stereo_extrinsics.v1",
            "left_camera_id": "cam1",
            "right_camera_id": "cam2",
            "rotation_left_to_right": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "translation_left_to_right_m": [0.2, 0, 0],
            "baseline_m": 0.2,
        },
    )
    write_json(
        package / "rectification.json",
        {
            "schema_version": "calibration.rectification.v1",
            "left_camera_id": "cam1",
            "right_camera_id": "cam2",
            "image_size": {"width": width, "height": height},
            "r1": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "r2": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "p1": [[1000, 0, width / 2, 0], [0, 1000, height / 2, 0], [0, 0, 1, 0]],
            "p2": [[1000, 0, width / 2, p2_offset], [0, 1000, height / 2, 0], [0, 0, 1, 0]],
        },
    )
    return package


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")
