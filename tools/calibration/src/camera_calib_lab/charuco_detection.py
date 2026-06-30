from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from camera_calib_lab.capture_types import CaptureConfig, CharucoDetection, TargetConfig


def create_charuco_board(target: TargetConfig) -> cv2.aruco.CharucoBoard:
    dictionary_id = getattr(cv2.aruco, target.dictionary)
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    try:
        return cv2.aruco.CharucoBoard(
            (target.squares_x, target.squares_y),
            target.square_size_m,
            target.marker_size_m,
            dictionary,
        )
    except TypeError:
        return cv2.aruco.CharucoBoard_create(
            target.squares_x,
            target.squares_y,
            target.square_size_m,
            target.marker_size_m,
            dictionary,
        )


def create_detector(board: cv2.aruco.CharucoBoard) -> Any:
    if hasattr(cv2.aruco, "CharucoDetector"):
        return cv2.aruco.CharucoDetector(board)
    return None


def detect_charuco(frame: np.ndarray, board: cv2.aruco.CharucoBoard, detector: Any) -> CharucoDetection:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
    mean_gray = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    corners = None
    ids = None
    if detector is not None:
        result = detector.detectBoard(gray)
        corners = result[0] if len(result) > 0 else None
        ids = result[1] if len(result) > 1 else None
    else:
        marker_corners, marker_ids, _rejected = cv2.aruco.detectMarkers(gray, board.getDictionary())
        if marker_ids is not None and len(marker_ids) > 0:
            _count, corners, ids = cv2.aruco.interpolateCornersCharuco(marker_corners, marker_ids, gray, board)
    points = charuco_points(corners, ids)
    return CharucoDetection(
        corners=corners,
        ids=ids,
        count=len(points),
        mean_gray=mean_gray,
        sharpness=sharpness,
        points=points,
    )


def charuco_points(corners: np.ndarray | None, ids: np.ndarray | None) -> tuple[tuple[float, float], ...]:
    if corners is None or ids is None:
        return ()
    array = np.asarray(corners, dtype=np.float64).reshape(-1, 2)
    return tuple((float(row[0]), float(row[1])) for row in array.tolist())


def detected_ids(detection: CharucoDetection) -> list[int]:
    if detection.ids is None:
        return []
    return [int(value) for value in np.asarray(detection.ids, dtype=np.int64).reshape(-1).tolist()]


def detection_is_accepted(detection: CharucoDetection, capture: CaptureConfig) -> bool:
    return detection.count >= capture.min_corners and detection.sharpness >= capture.min_sharpness
