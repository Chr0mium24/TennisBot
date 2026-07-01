from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from camera_calib_lab.capture_types import TargetConfig, utc_now_iso
from camera_calib_lab.charuco_detection import create_charuco_board, create_detector, detect_charuco


MONO_SCHEMA = "calibration.mono.v1"
STEREO_SCHEMA = "calibration.stereo.v1"
CAMERA_SCHEMA = "calibration.camera_intrinsics.v1"
STEREO_EXTRINSICS_SCHEMA = "calibration.stereo_extrinsics.v1"
RECTIFICATION_SCHEMA = "calibration.rectification.v1"


@dataclass(frozen=True)
class ViewObservation:
    camera_id: str
    side: str | None
    index: int
    image_size: tuple[int, int]
    object_points: np.ndarray
    image_points: np.ndarray
    ids: np.ndarray | None
    path: str | None = None


@dataclass(frozen=True)
class SourceObservations:
    topology: str
    source_path: Path
    target: dict[str, Any]
    dry_run: bool
    hardware_validated: bool
    views: list[ViewObservation]
    pair_indices: list[int]
    devices: dict[str, str]


@dataclass(frozen=True)
class MonoCameraPackage:
    package_dir: Path
    package_json: dict[str, Any]
    camera_json: dict[str, Any]
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    source_device: str | None = None


def solve_mono_package(
    *,
    session_path: Path | None,
    observations_path: Path | None,
    output_path: Path,
    config_path: Path,
    camera_id: str | None,
    min_views: int,
    max_rms_px: float,
) -> dict[str, Any]:
    source = load_source_observations(session_path=session_path, observations_path=observations_path, config_path=config_path)
    if source.topology != "mono":
        raise ValueError(f"mono solve requires a mono source, got topology={source.topology!r}")
    views = source.views if camera_id in {None, ""} else [view for view in source.views if view.camera_id == camera_id]
    if not views:
        if camera_id not in {None, ""}:
            raise ValueError(f"no accepted mono ChArUco views were found for camera_id={camera_id!r}")
        raise ValueError("no accepted mono ChArUco views were found")
    image_size = common_image_size(views)
    object_points = [view.object_points for view in views]
    image_points = [view.image_points for view in views]
    flags = cv2.CALIB_RATIONAL_MODEL
    rms_px, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
        flags=flags,
    )
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(camera_matrix, dist_coeffs, image_size, 1.0, image_size)
    accepted_view_count = len(views)
    accepted = accepted_view_count >= min_views and float(rms_px) <= max_rms_px
    resolved_camera_id = camera_id or views[0].camera_id
    source_device = source_device_for_views(source, views)
    target = target_payload(source.target)
    created_at = utc_now_iso()
    camera_json = camera_intrinsics_json(
        camera_id=resolved_camera_id,
        image_size=image_size,
        camera_matrix=camera_matrix,
        dist_coeffs=dist_coeffs,
        new_camera_matrix=new_camera_matrix,
        roi=roi,
    )
    verification_json = {
        "schema_version": "calibration.verification.v1",
        "accepted": accepted,
        "dry_run": source.dry_run,
        "hardware_validated": source.hardware_validated,
        "checks": [
            {
                "name": "accepted_view_count",
                "passed": accepted_view_count >= min_views,
                "value": accepted_view_count,
                "minimum": min_views,
            },
            {
                "name": "rms_reprojection_px",
                "passed": float(rms_px) <= max_rms_px,
                "value": float(rms_px),
                "threshold": max_rms_px,
            },
        ],
        "coverage": {
            "accepted_view_count": accepted_view_count,
            "corner_count_min": min(int(view.image_points.shape[0]) for view in views),
            "corner_count_max": max(int(view.image_points.shape[0]) for view in views),
        },
    }
    package_json = {
        "schema_version": MONO_SCHEMA,
        "package_type": "mono_camera_calibration",
        "camera_id": resolved_camera_id,
        "created_at": created_at,
        "source_session": display_source_path(source.source_path),
        "source_device": source_device,
        "target": target,
        "files": {
            "camera": "camera.json",
            "opencv_yaml": "calibration_opencv.yaml",
            "verification": "verification.json",
            "summary": "summary.md",
            "review_html": "review.html",
        },
        "image_size": image_size_json(image_size),
        "quality": {
            "accepted": accepted,
            "accepted_view_count": accepted_view_count,
            "total_view_count": len(source.views),
            "rms_reprojection_px": float(rms_px),
            "max_rms_px": max_rms_px,
        },
        "accepted": accepted,
        "dry_run": source.dry_run,
        "hardware_validated": source.hardware_validated,
    }
    output_path.mkdir(parents=True, exist_ok=True)
    write_json(output_path / "camera.json", camera_json)
    write_json(output_path / "verification.json", verification_json)
    write_json(output_path / "package.json", package_json)
    write_text(output_path / "summary.md", mono_summary(package_json, verification_json))
    write_text(output_path / "review.html", mono_review(package_json, verification_json))
    write_text(
        output_path / "calibration_opencv.yaml",
        mono_opencv_yaml(resolved_camera_id, camera_matrix, dist_coeffs),
    )
    return package_json


def solve_stereo_package(
    *,
    session_path: Path | None,
    observations_path: Path | None,
    left_mono_path: Path,
    right_mono_path: Path,
    output_path: Path,
    config_path: Path,
    left_camera_id: str,
    right_camera_id: str,
    min_pairs: int,
    max_rms_px: float,
    epipolar_warning_px: float,
    rectification_warning_px: float,
) -> dict[str, Any]:
    source = load_source_observations(session_path=session_path, observations_path=observations_path, config_path=config_path)
    if source.topology != "stereo":
        raise ValueError(f"stereo solve requires a stereo source, got topology={source.topology!r}")
    left_mono = load_mono_package(left_mono_path)
    right_mono = load_mono_package(right_mono_path)
    validate_mono_package(left_mono, expected_camera_id=left_camera_id)
    validate_mono_package(right_mono, expected_camera_id=right_camera_id)
    validate_stereo_source_devices(source, left_mono=left_mono, right_mono=right_mono)
    pairs = stereo_pairs(source)
    if not pairs:
        raise ValueError("no accepted stereo ChArUco pairs were found")
    image_size = common_image_size([view for pair in pairs for view in pair[:2]])
    object_points = []
    left_image_points = []
    right_image_points = []
    matched_counts: list[int] = []
    for left, right in pairs:
        obj, left_img, right_img = align_stereo_pair(left, right)
        object_points.append(obj)
        left_image_points.append(left_img)
        right_image_points.append(right_img)
        matched_counts.append(int(obj.shape[0]))
    flags = cv2.CALIB_FIX_INTRINSIC
    (
        stereo_rms,
        left_k,
        left_dist,
        right_k,
        right_dist,
        rotation,
        translation,
        essential,
        fundamental,
    ) = cv2.stereoCalibrate(
        object_points,
        left_image_points,
        right_image_points,
        left_mono.camera_matrix.copy(),
        left_mono.dist_coeffs.copy(),
        right_mono.camera_matrix.copy(),
        right_mono.dist_coeffs.copy(),
        image_size,
        flags=flags,
    )
    r1, r2, p1, p2, q, roi1, roi2 = cv2.stereoRectify(
        left_k,
        left_dist,
        right_k,
        right_dist,
        image_size,
        rotation,
        translation,
    )
    epipolar_rms = epipolar_rms_px(left_image_points, right_image_points, fundamental)
    rectification_y_p95 = rectification_y_p95_px(
        left_image_points,
        right_image_points,
        left_k,
        left_dist,
        right_k,
        right_dist,
        r1,
        r2,
        p1,
        p2,
    )
    baseline_m = float(np.linalg.norm(translation.reshape(-1)))
    accepted_pair_count = len(pairs)
    warnings = []
    if epipolar_rms is not None and epipolar_rms > epipolar_warning_px:
        warnings.append(f"epipolar_rms_px={epipolar_rms:.3f} exceeds runtime-quality review threshold {epipolar_warning_px:.3f}")
    if rectification_y_p95 is not None and rectification_y_p95 > rectification_warning_px:
        warnings.append(
            f"rectification_y_p95_px={rectification_y_p95:.3f} exceeds runtime-quality review threshold {rectification_warning_px:.3f}"
        )
    accepted = accepted_pair_count >= min_pairs and float(stereo_rms) <= max_rms_px and baseline_m > 0
    created_at = utc_now_iso()
    target = target_payload(source.target)
    left_camera_json = left_mono.camera_json
    right_camera_json = right_mono.camera_json
    stereo_json = {
        "schema_version": STEREO_EXTRINSICS_SCHEMA,
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "rotation_left_to_right": matrix_json(rotation, shape=(3, 3)),
        "translation_left_to_right_m": vector_json(translation.reshape(-1), length=3),
        "essential_matrix": matrix_json(essential, shape=(3, 3)),
        "fundamental_matrix": matrix_json(fundamental, shape=(3, 3)),
        "baseline_m": baseline_m,
        "source_method_id": "stereo.opencv_extrinsics",
        "source_metrics": {
            "accepted_pairs": accepted_pair_count,
            "stereo_rms_px": float(stereo_rms),
            "epipolar_rms_px": epipolar_rms,
            "rectification_y_p95_px": rectification_y_p95,
            "matched_point_count_min": min(matched_counts),
            "baseline_m": baseline_m,
        },
    }
    rectification_json = {
        "schema_version": RECTIFICATION_SCHEMA,
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "image_size": image_size_json(image_size),
        "r1": matrix_json(r1, shape=(3, 3)),
        "r2": matrix_json(r2, shape=(3, 3)),
        "p1": matrix_json(p1, shape=(3, 4)),
        "p2": matrix_json(p2, shape=(3, 4)),
        "q": matrix_json(q, shape=(4, 4)),
        "left_roi": roi_json(roi1),
        "right_roi": roi_json(roi2),
    }
    checks = [
        {
            "name": "accepted_pair_count",
            "passed": accepted_pair_count >= min_pairs,
            "value": accepted_pair_count,
            "minimum": min_pairs,
        },
        {
            "name": "stereo_rms_px",
            "passed": float(stereo_rms) <= max_rms_px,
            "value": float(stereo_rms),
            "threshold": max_rms_px,
        },
        {
            "name": "epipolar_rms_px",
            "passed": True,
            "value": epipolar_rms,
            "warning": epipolar_rms is not None and epipolar_rms > epipolar_warning_px,
            "warning_threshold": epipolar_warning_px,
        },
        {
            "name": "rectification_y_p95_px",
            "passed": True,
            "value": rectification_y_p95,
            "warning": rectification_y_p95 is not None and rectification_y_p95 > rectification_warning_px,
            "warning_threshold": rectification_warning_px,
        },
        {
            "name": "baseline_m",
            "passed": baseline_m > 0,
            "value": baseline_m,
            "minimum": 0,
        },
    ]
    verification_json = {
        "schema_version": "calibration.stereo_verification.v1",
        "accepted": accepted,
        "dry_run": source.dry_run,
        "hardware_validated": source.hardware_validated,
        "checks": checks,
        "rectification": {
            "accepted": True,
            "epipolar_error_px": epipolar_rms,
            "rectification_y_p95_px": rectification_y_p95,
        },
        "warnings": warnings,
    }
    package_json = {
        "schema_version": STEREO_SCHEMA,
        "package_type": "stereo_camera_calibration",
        "camera_ids": [left_camera_id, right_camera_id],
        "created_at": created_at,
        "source_session": display_source_path(source.source_path),
        "mono_sources": {
            left_camera_id: display_source_path(left_mono_path),
            right_camera_id: display_source_path(right_mono_path),
        },
        "target": target,
        "files": {
            "cam1": "cam1.json",
            "cam2": "cam2.json",
            "stereo": "stereo.json",
            "rectification": "rectification.json",
            "opencv_yaml": "calibration_opencv.yaml",
            "verification": "verification.json",
            "summary": "summary.md",
            "review_html": "review.html",
        },
        "quality": {
            "accepted": accepted,
            "accepted_pair_count": accepted_pair_count,
            "total_pair_count": len(source.pair_indices) or accepted_pair_count,
            "stereo_rms_reprojection_px": float(stereo_rms),
            "max_rms_px": max_rms_px,
            "epipolar_rms_px": epipolar_rms,
            "rectification_y_p95_px": rectification_y_p95,
            "matched_point_count_min": min(matched_counts),
            "baseline_m": baseline_m,
            "warnings": warnings,
        },
        "runtime_quality_warning": len(warnings) > 0,
        "accepted": accepted,
        "dry_run": source.dry_run,
        "hardware_validated": source.hardware_validated,
    }
    output_path.mkdir(parents=True, exist_ok=True)
    write_json(output_path / "cam1.json", left_camera_json)
    write_json(output_path / "cam2.json", right_camera_json)
    write_json(output_path / "stereo.json", stereo_json)
    write_json(output_path / "rectification.json", rectification_json)
    write_json(output_path / "verification.json", verification_json)
    write_json(output_path / "package.json", package_json)
    write_text(output_path / "summary.md", stereo_summary(package_json, verification_json))
    write_text(output_path / "review.html", stereo_review(package_json, verification_json))
    write_text(
        output_path / "calibration_opencv.yaml",
        stereo_opencv_yaml(
            left_camera_id=left_camera_id,
            right_camera_id=right_camera_id,
            left_camera_matrix=left_k,
            left_dist_coeffs=left_dist,
            right_camera_matrix=right_k,
            right_dist_coeffs=right_dist,
            rotation=rotation,
            translation=translation,
            r1=r1,
            r2=r2,
            p1=p1,
            p2=p2,
            q=q,
        ),
    )
    return package_json


def load_source_observations(*, session_path: Path | None, observations_path: Path | None, config_path: Path) -> SourceObservations:
    if observations_path is not None:
        return load_observations_json(observations_path)
    if session_path is None:
        raise ValueError("either --session or --observations is required")
    return detect_session_observations(session_path, config_path)


def load_observations_json(path: Path) -> SourceObservations:
    payload = json.loads(path.read_text(encoding="utf-8"))
    views = []
    for item in payload.get("views", []):
        if item.get("accepted") is not True:
            continue
        image_size = item.get("image_size") or payload.get("image_size")
        if not isinstance(image_size, dict):
            raise ValueError(f"observation view {item.get('index')} is missing image_size")
        views.append(
            ViewObservation(
                camera_id=str(item.get("camera_id", "")),
                side=str(item["side"]) if item.get("side") is not None else None,
                index=int(item.get("index", len(views) + 1)),
                image_size=(int(image_size["width"]), int(image_size["height"])),
                object_points=points_array(item["object_points"], dims=3),
                image_points=points_array(item["image_points"], dims=2),
                ids=ids_array(item.get("ids")),
                path=str(item["path"]) if item.get("path") is not None else None,
            )
        )
    pair_indices = [int(pair.get("index")) for pair in payload.get("pairs", []) if pair.get("accepted") is True and pair.get("index") is not None]
    return SourceObservations(
        topology=str(payload.get("topology", "mono")),
        source_path=path,
        target=dict(payload.get("target", {})),
        dry_run=bool(payload.get("dry_run", False)),
        hardware_validated=bool(payload.get("hardware_validated", not bool(payload.get("dry_run", False)))),
        views=views,
        pair_indices=pair_indices,
        devices={},
    )


def detect_session_observations(session_path: Path, _config_path: Path) -> SourceObservations:
    session_file = session_path / "session.json"
    payload = json.loads(session_file.read_text(encoding="utf-8"))
    if not isinstance(payload.get("frames"), list):
        raise ValueError("capture session.json is missing frames")
    target = dict(payload.get("target", {}))
    topology = session_topology(payload)
    target_config = target_config_from_payload(target)
    board = create_charuco_board(target_config)
    detector = create_detector(board)
    views: list[ViewObservation] = []
    pair_indices: list[int] = []
    if topology == "mono":
        for index, item in enumerate(mono_session_frames(payload), start=1):
            views.append(
                detect_image_observation(
                    session_frame_path(session_path, item["image"]),
                    board,
                    detector,
                    item["camera_id"],
                    None,
                    index,
                )
            )
    elif topology == "stereo":
        for index, pair in enumerate(stereo_session_pairs(payload), start=1):
            left = detect_image_observation(
                session_frame_path(session_path, pair["left_image"]),
                board,
                detector,
                pair["left_camera_id"],
                "left",
                index,
            )
            right = detect_image_observation(
                session_frame_path(session_path, pair["right_image"]),
                board,
                detector,
                pair["right_camera_id"],
                "right",
                index,
            )
            if left.image_points.shape[0] > 0 and right.image_points.shape[0] > 0:
                pair_indices.append(index)
            views.extend([left, right])
    else:
        raise ValueError(f"unsupported session topology: {topology}")
    dry_run = bool(payload.get("dry_run", False))
    hardware_validated = bool(payload.get("hardware_validated", not dry_run))
    return SourceObservations(
        topology=topology,
        source_path=session_path,
        target=target,
        dry_run=dry_run,
        hardware_validated=hardware_validated,
        views=[view for view in views if view.image_points.shape[0] > 0],
        pair_indices=pair_indices,
        devices=session_devices(payload, topology),
    )


def detect_image_observation(
    image_path: Path,
    board: cv2.aruco.CharucoBoard,
    detector: Any,
    camera_id: str,
    side: str | None,
    index: int,
) -> ViewObservation:
    frame = cv2.imread(str(image_path))
    if frame is None:
        raise ValueError(f"failed to read image: {image_path}")
    detection = detect_charuco(frame, board, detector)
    object_points, image_points, ids = charuco_points(board, detection.corners, detection.ids)
    height, width = frame.shape[:2]
    return ViewObservation(
        camera_id=camera_id,
        side=side,
        index=index,
        image_size=(width, height),
        object_points=object_points,
        image_points=image_points,
        ids=ids,
        path=str(image_path),
    )


def session_topology(payload: dict[str, Any]) -> str:
    if "topology" in payload:
        return str(payload["topology"])
    raise ValueError("capture session.json does not declare topology")


def session_devices(payload: dict[str, Any], topology: str) -> dict[str, str]:
    if topology == "mono":
        camera = payload.get("camera")
        if not isinstance(camera, dict):
            raise ValueError("mono session.json is missing camera")
        device = camera.get("device")
        return {} if device in {None, ""} else {str(camera["camera_id"]): str(device)}
    if topology == "stereo":
        rig = payload.get("stereo_rig")
        if not isinstance(rig, dict):
            raise ValueError("stereo session.json is missing stereo_rig")
        left = rig.get("left")
        right = rig.get("right")
        if not isinstance(left, dict) or not isinstance(right, dict):
            raise ValueError("stereo session.json stereo_rig is missing left or right camera")
        devices = {}
        if left.get("device") not in {None, ""}:
            devices["left"] = str(left["device"])
        if right.get("device") not in {None, ""}:
            devices["right"] = str(right["device"])
        return devices
    return {}


def mono_session_frames(payload: dict[str, Any]) -> list[dict[str, str]]:
    frames = []
    for item in payload["frames"]:
        frame_paths = item.get("frame_paths")
        if not isinstance(frame_paths, list) or not frame_paths:
            raise ValueError(f"mono frame {item.get('view_id')} is missing frame_paths")
        frames.append(
            {
                "camera_id": str(item["camera_id"]),
                "image": str(frame_paths[0]),
            }
        )
    return frames


def stereo_session_pairs(payload: dict[str, Any]) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, str]] = {}
    for item in payload["frames"]:
        view_id = str(item.get("view_id", ""))
        camera_id = str(item.get("camera_id", ""))
        frame_paths = item.get("frame_paths")
        if not view_id or not isinstance(frame_paths, list) or not frame_paths:
            raise ValueError("stereo frame is missing view_id or frame_paths")
        if camera_id not in {"left", "right"}:
            raise ValueError(f"stereo frame camera_id must be left or right, got {camera_id!r}")
        grouped.setdefault(view_id, {})[camera_id] = str(frame_paths[0])
    pairs = []
    for view_id in sorted(grouped):
        pair = grouped[view_id]
        if "left" not in pair or "right" not in pair:
            raise ValueError(f"stereo view {view_id} is missing left or right frame")
        pairs.append(
            {
                "left_camera_id": "left",
                "right_camera_id": "right",
                "left_image": pair["left"],
                "right_image": pair["right"],
            }
        )
    return pairs


def session_frame_path(session_path: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else session_path / path


def target_config_from_payload(payload: dict[str, Any]) -> TargetConfig:
    return TargetConfig(
        profile=str(payload["profile"]),
        squares_x=int(payload["squares_x"]),
        squares_y=int(payload["squares_y"]),
        dictionary=str(payload["dictionary"]),
        square_size_m=float(payload["square_size_m"]),
        marker_size_m=float(payload["marker_size_m"]),
    )


def target_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": str(payload.get("type", "charuco")),
        "profile": str(payload.get("profile", "dfoptix_charuco_14x9_square15mm_marker11_25mm")),
        "dictionary": str(payload.get("dictionary", "DICT_5X5_100")),
        "squares_x": int(payload.get("squares_x", 14)),
        "squares_y": int(payload.get("squares_y", 9)),
        "square_size_m": float(payload.get("square_size_m", 0.015)),
        "marker_size_m": float(payload.get("marker_size_m", 0.01125)),
    }


def charuco_points(
    board: cv2.aruco.CharucoBoard,
    corners: np.ndarray | None,
    ids: np.ndarray | None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    if corners is None or ids is None or len(ids) == 0:
        return empty_object_points(), empty_image_points(), None
    flat_ids = ids.astype(np.int32).reshape(-1)
    image = corners.astype(np.float32).reshape(-1, 1, 2)
    board_points = np.asarray(board.getChessboardCorners(), dtype=np.float32).reshape(-1, 3)
    object_points = board_points[flat_ids].reshape(-1, 1, 3)
    return object_points, image, flat_ids


def empty_object_points() -> np.ndarray:
    return np.empty((0, 1, 3), dtype=np.float32)


def empty_image_points() -> np.ndarray:
    return np.empty((0, 1, 2), dtype=np.float32)


def points_array(value: Any, *, dims: int) -> np.ndarray:
    array = np.asarray(value, dtype=np.float32)
    if array.ndim == 2 and array.shape[1] == dims:
        return array.reshape(-1, 1, dims)
    if array.ndim == 3 and array.shape[1] == 1 and array.shape[2] == dims:
        return array
    raise ValueError(f"expected points shaped Nx{dims}, got {array.shape}")


def ids_array(value: Any) -> np.ndarray | None:
    if value is None:
        return None
    return np.asarray(value, dtype=np.int32).reshape(-1)


def common_image_size(views: list[ViewObservation]) -> tuple[int, int]:
    sizes = {view.image_size for view in views}
    if len(sizes) != 1:
        raise ValueError(f"all calibration views must share one image size, got {sorted(sizes)}")
    return next(iter(sizes))


def stereo_pairs(source: SourceObservations) -> list[tuple[ViewObservation, ViewObservation]]:
    views_by_index: dict[int, list[ViewObservation]] = {}
    for view in source.views:
        views_by_index.setdefault(view.index, []).append(view)
    pairs = []
    allowed_indices = set(source.pair_indices)
    for index, views in sorted(views_by_index.items()):
        if allowed_indices and index not in allowed_indices:
            continue
        left = first_view(views, side="left")
        right = first_view(views, side="right")
        if left is not None and right is not None:
            pairs.append((left, right))
    return pairs


def first_view(views: list[ViewObservation], *, side: str) -> ViewObservation | None:
    for view in views:
        if view.side == side:
            return view
    return None


def source_device_for_views(source: SourceObservations, views: list[ViewObservation]) -> str | None:
    camera_ids = {view.camera_id for view in views}
    if len(camera_ids) != 1:
        return None
    return source.devices.get(next(iter(camera_ids)))


def validate_stereo_source_devices(
    source: SourceObservations,
    *,
    left_mono: MonoCameraPackage,
    right_mono: MonoCameraPackage,
) -> None:
    left_device = source.devices.get("left")
    right_device = source.devices.get("right")
    if left_device is None and right_device is None:
        return
    validate_mono_source_device("left", left_mono, left_device)
    validate_mono_source_device("right", right_mono, right_device)


def validate_mono_source_device(side: str, package: MonoCameraPackage, expected_device: str | None) -> None:
    if expected_device is None:
        return
    actual_device = package.source_device
    if actual_device in {None, ""}:
        raise ValueError(f"{side} mono package {package.package_dir} is missing source_device")
    if normalize_device(actual_device) != normalize_device(expected_device):
        raise ValueError(
            f"{side} mono package {package.package_dir} source_device={actual_device!r} "
            f"does not match stereo {side} device {expected_device!r}"
        )


def normalize_device(value: str) -> str:
    if value.isdigit():
        return f"video:{int(value)}"
    match = re.fullmatch(r"/dev/video(\d+)", value)
    if match:
        return f"video:{int(match.group(1))}"
    return value


def align_stereo_pair(left: ViewObservation, right: ViewObservation) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    if left.ids is not None and right.ids is not None:
        left_ids = left.ids.reshape(-1)
        right_ids = right.ids.reshape(-1)
        common = sorted(set(int(value) for value in left_ids).intersection(int(value) for value in right_ids))
        if not common:
            raise ValueError(f"stereo pair {left.index} has no common ChArUco ids")
        left_index = {int(value): idx for idx, value in enumerate(left_ids)}
        right_index = {int(value): idx for idx, value in enumerate(right_ids)}
        object_points = np.asarray([left.object_points[left_index[item], 0, :] for item in common], dtype=np.float32).reshape(-1, 1, 3)
        left_points = np.asarray([left.image_points[left_index[item], 0, :] for item in common], dtype=np.float32).reshape(-1, 1, 2)
        right_points = np.asarray([right.image_points[right_index[item], 0, :] for item in common], dtype=np.float32).reshape(-1, 1, 2)
        return object_points, left_points, right_points
    if left.object_points.shape[0] != right.object_points.shape[0]:
        raise ValueError(f"stereo pair {left.index} point counts differ and ids are unavailable")
    return left.object_points, left.image_points, right.image_points


def load_mono_package(package_dir: Path) -> MonoCameraPackage:
    package_json = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    camera_file = package_json.get("files", {}).get("camera", "camera.json")
    camera_json = json.loads((package_dir / camera_file).read_text(encoding="utf-8"))
    return MonoCameraPackage(
        package_dir=package_dir,
        package_json=package_json,
        camera_json=camera_json,
        camera_matrix=np.asarray(camera_json["camera_matrix"], dtype=np.float64),
        dist_coeffs=np.asarray(camera_json["distortion_coefficients"], dtype=np.float64).reshape(-1, 1),
        source_device=str(package_json["source_device"]) if package_json.get("source_device") not in {None, ""} else None,
    )


def validate_mono_package(package: MonoCameraPackage, *, expected_camera_id: str) -> None:
    actual_camera_id = str(package.camera_json.get("camera_id", ""))
    if actual_camera_id != expected_camera_id:
        raise ValueError(
            f"mono package {package.package_dir} camera_id={actual_camera_id!r} does not match expected {expected_camera_id!r}"
        )
    if package.package_json.get("accepted") is not True:
        raise ValueError(f"mono package {package.package_dir} is not accepted")


def camera_intrinsics_json(
    *,
    camera_id: str,
    image_size: tuple[int, int],
    camera_matrix: np.ndarray,
    dist_coeffs: np.ndarray,
    new_camera_matrix: np.ndarray,
    roi: tuple[int, int, int, int],
) -> dict[str, Any]:
    return {
        "schema_version": CAMERA_SCHEMA,
        "camera_id": camera_id,
        "image_size": image_size_json(image_size),
        "camera_matrix": matrix_json(camera_matrix, shape=(3, 3)),
        "distortion_model": "opencv_rational",
        "distortion_coefficients": vector_json(dist_coeffs.reshape(-1), length=None),
        "new_camera_matrix": matrix_json(new_camera_matrix, shape=(3, 3)),
        "roi": roi_json(roi),
    }


def epipolar_rms_px(
    left_points_by_view: list[np.ndarray],
    right_points_by_view: list[np.ndarray],
    fundamental: np.ndarray,
) -> float | None:
    left = np.concatenate([points.reshape(-1, 2) for points in left_points_by_view], axis=0)
    right = np.concatenate([points.reshape(-1, 2) for points in right_points_by_view], axis=0)
    if left.size == 0 or right.size == 0:
        return None
    lines_right = cv2.computeCorrespondEpilines(left.reshape(-1, 1, 2), 1, fundamental).reshape(-1, 3)
    lines_left = cv2.computeCorrespondEpilines(right.reshape(-1, 1, 2), 2, fundamental).reshape(-1, 3)
    right_dist = line_distances(lines_right, right)
    left_dist = line_distances(lines_left, left)
    return float(np.sqrt(np.mean(np.concatenate([left_dist, right_dist]) ** 2)))


def line_distances(lines: np.ndarray, points: np.ndarray) -> np.ndarray:
    numerator = np.abs(lines[:, 0] * points[:, 0] + lines[:, 1] * points[:, 1] + lines[:, 2])
    denominator = np.sqrt(lines[:, 0] ** 2 + lines[:, 1] ** 2)
    return numerator / np.maximum(denominator, 1.0e-12)


def rectification_y_p95_px(
    left_points_by_view: list[np.ndarray],
    right_points_by_view: list[np.ndarray],
    left_k: np.ndarray,
    left_dist: np.ndarray,
    right_k: np.ndarray,
    right_dist: np.ndarray,
    r1: np.ndarray,
    r2: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
) -> float | None:
    left = np.concatenate([points.reshape(-1, 2) for points in left_points_by_view], axis=0)
    right = np.concatenate([points.reshape(-1, 2) for points in right_points_by_view], axis=0)
    if left.size == 0 or right.size == 0:
        return None
    left_rect = cv2.undistortPoints(left.reshape(-1, 1, 2), left_k, left_dist, R=r1, P=p1).reshape(-1, 2)
    right_rect = cv2.undistortPoints(right.reshape(-1, 1, 2), right_k, right_dist, R=r2, P=p2).reshape(-1, 2)
    return float(np.percentile(np.abs(left_rect[:, 1] - right_rect[:, 1]), 95))


def image_size_json(image_size: tuple[int, int]) -> dict[str, int]:
    width, height = image_size
    return {"width": int(width), "height": int(height)}


def roi_json(roi: tuple[int, int, int, int] | Any) -> dict[str, int]:
    x, y, width, height = [int(value) for value in roi]
    return {"x": x, "y": y, "width": width, "height": height}


def matrix_json(matrix: np.ndarray, *, shape: tuple[int, int]) -> list[list[float]]:
    array = np.asarray(matrix, dtype=float).reshape(shape)
    return [[float(value) for value in row] for row in array.tolist()]


def vector_json(vector: np.ndarray, *, length: int | None) -> list[float]:
    array = np.asarray(vector, dtype=float).reshape(-1)
    if length is not None and len(array) != length:
        raise ValueError(f"expected vector length {length}, got {len(array)}")
    return [float(value) for value in array.tolist()]


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def display_source_path(path: Path) -> str:
    return path.as_posix()


def mono_summary(package_json: dict[str, Any], verification_json: dict[str, Any]) -> str:
    quality = package_json["quality"]
    checks = verification_json["checks"]
    lines = [
        "# Mono Calibration Package",
        "",
        f"- camera_id: {package_json['camera_id']}",
        f"- created_at: {package_json['created_at']}",
        f"- accepted: {package_json['accepted']}",
        f"- dry_run: {package_json['dry_run']}",
        f"- hardware_validated: {package_json['hardware_validated']}",
        f"- source_session: {package_json['source_session']}",
        f"- rms_reprojection_px: {quality['rms_reprojection_px']}",
        f"- accepted_view_count: {quality['accepted_view_count']} / {quality['total_view_count']}",
        "",
        "## Checks",
        "",
        *[f"- {check['name']}: passed={check['passed']} value={check.get('value')}" for check in checks],
        "",
    ]
    return "\n".join(lines)


def stereo_summary(package_json: dict[str, Any], verification_json: dict[str, Any]) -> str:
    quality = package_json["quality"]
    checks = verification_json["checks"]
    lines = [
        "# Stereo Calibration Package",
        "",
        f"- camera_ids: {', '.join(package_json['camera_ids'])}",
        f"- created_at: {package_json['created_at']}",
        f"- accepted: {package_json['accepted']}",
        f"- dry_run: {package_json['dry_run']}",
        f"- hardware_validated: {package_json['hardware_validated']}",
        f"- runtime_quality_warning: {package_json['runtime_quality_warning']}",
        f"- source_session: {package_json['source_session']}",
        f"- stereo_rms_reprojection_px: {quality['stereo_rms_reprojection_px']}",
        f"- epipolar_rms_px: {quality['epipolar_rms_px']}",
        f"- rectification_y_p95_px: {quality['rectification_y_p95_px']}",
        f"- baseline_m: {quality['baseline_m']}",
        f"- accepted_pair_count: {quality['accepted_pair_count']} / {quality['total_pair_count']}",
        "",
        "## Checks",
        "",
        *[f"- {check['name']}: passed={check['passed']} value={check.get('value')}" for check in checks],
    ]
    if quality["warnings"]:
        lines.extend(["", "## Warnings", "", *[f"- {warning}" for warning in quality["warnings"]]])
    lines.append("")
    return "\n".join(lines)


def mono_review(package_json: dict[str, Any], verification_json: dict[str, Any]) -> str:
    quality = package_json["quality"]
    return simple_review_html(
        "Mono Calibration Package",
        [
            ("camera_id", package_json["camera_id"]),
            ("accepted", package_json["accepted"]),
            ("dry_run", package_json["dry_run"]),
            ("hardware_validated", package_json["hardware_validated"]),
            ("rms_reprojection_px", quality["rms_reprojection_px"]),
            ("verification_accepted", verification_json["accepted"]),
        ],
    )


def stereo_review(package_json: dict[str, Any], verification_json: dict[str, Any]) -> str:
    quality = package_json["quality"]
    fields = [
        ("camera_ids", ", ".join(package_json["camera_ids"])),
        ("accepted", package_json["accepted"]),
        ("dry_run", package_json["dry_run"]),
        ("hardware_validated", package_json["hardware_validated"]),
        ("stereo_rms_reprojection_px", quality["stereo_rms_reprojection_px"]),
        ("epipolar_rms_px", quality["epipolar_rms_px"]),
        ("rectification_y_p95_px", quality["rectification_y_p95_px"]),
        ("baseline_m", quality["baseline_m"]),
        ("verification_accepted", verification_json["accepted"]),
    ]
    return simple_review_html("Stereo Calibration Package", fields, warnings=quality["warnings"])


def simple_review_html(title: str, fields: list[tuple[str, Any]], warnings: list[str] | None = None) -> str:
    warning_block = ""
    if warnings:
        warning_block = "<h2>Warnings</h2><ul>" + "".join(f"<li>{html.escape(item)}</li>" for item in warnings) + "</ul>"
    rows = "\n".join(f"<p><code>{html.escape(key)}</code>: {html.escape(str(value))}</p>" for key, value in fields)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{html.escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #111827; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  {rows}
  {warning_block}
</body>
</html>
"""


def mono_opencv_yaml(camera_id: str, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> str:
    return "\n".join(
        [
            "%YAML:1.0",
            "---",
            "schema_version: calibration.opencv.v1",
            "topology: mono",
            f"camera_id: {camera_id}",
            f"camera_matrix: {matrix_json(camera_matrix, shape=(3, 3))}",
            f"dist_coeffs: {vector_json(dist_coeffs.reshape(-1), length=None)}",
            "",
        ]
    )


def stereo_opencv_yaml(
    *,
    left_camera_id: str,
    right_camera_id: str,
    left_camera_matrix: np.ndarray,
    left_dist_coeffs: np.ndarray,
    right_camera_matrix: np.ndarray,
    right_dist_coeffs: np.ndarray,
    rotation: np.ndarray,
    translation: np.ndarray,
    r1: np.ndarray,
    r2: np.ndarray,
    p1: np.ndarray,
    p2: np.ndarray,
    q: np.ndarray,
) -> str:
    return "\n".join(
        [
            "%YAML:1.0",
            "---",
            "schema_version: calibration.opencv.v1",
            "topology: stereo",
            f"left_camera_id: {left_camera_id}",
            f"right_camera_id: {right_camera_id}",
            f"left_camera_matrix: {matrix_json(left_camera_matrix, shape=(3, 3))}",
            f"left_dist_coeffs: {vector_json(left_dist_coeffs.reshape(-1), length=None)}",
            f"right_camera_matrix: {matrix_json(right_camera_matrix, shape=(3, 3))}",
            f"right_dist_coeffs: {vector_json(right_dist_coeffs.reshape(-1), length=None)}",
            f"rotation: {matrix_json(rotation, shape=(3, 3))}",
            f"translation: {vector_json(translation.reshape(-1), length=3)}",
            f"rectification_r1: {matrix_json(r1, shape=(3, 3))}",
            f"rectification_r2: {matrix_json(r2, shape=(3, 3))}",
            f"projection_p1: {matrix_json(p1, shape=(3, 4))}",
            f"projection_p2: {matrix_json(p2, shape=(3, 4))}",
            f"disparity_q: {matrix_json(q, shape=(4, 4))}",
            "",
        ]
    )
