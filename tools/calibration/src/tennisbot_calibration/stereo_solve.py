from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.artifacts import write_opencv_yaml
from tennisbot_calibration.capture_sessions import now_utc
from tennisbot_calibration.io import read_json, write_json


def solve_stereo_calibration(
    *,
    observations_path: Path,
    left_mono: Path,
    right_mono: Path,
    output: Path,
    min_pairs: int = 8,
    min_common_corners: int = 12,
    max_rms_px: float = 2.0,
) -> dict[str, Any]:
    if min_pairs <= 0:
        raise ValueError("min_pairs must be positive")
    if min_common_corners <= 0:
        raise ValueError("min_common_corners must be positive")
    if max_rms_px <= 0:
        raise ValueError("max_rms_px must be positive")

    observations = json.loads(observations_path.read_text(encoding="utf-8"))
    if observations.get("topology") != "stereo":
        raise ValueError("stereo solve requires stereo observations")
    left_camera = read_json(left_mono / "camera.json")
    right_camera = read_json(right_mono / "camera.json")
    left_camera_id = str(left_camera["camera_id"])
    right_camera_id = str(right_camera["camera_id"])
    matched_pairs = matched_stereo_points(observations, left_camera_id, right_camera_id, min_common_corners)
    if len(matched_pairs) < min_pairs:
        raise RuntimeError(f"accepted pair count {len(matched_pairs)} is below required minimum {min_pairs}")

    image_size = common_pair_image_size(matched_pairs)
    object_points = [pair["object_points"] for pair in matched_pairs]
    left_points = [pair["left_image_points"] for pair in matched_pairs]
    right_points = [pair["right_image_points"] for pair in matched_pairs]
    left_matrix = np.asarray(left_camera["camera_matrix"], dtype=np.float64)
    right_matrix = np.asarray(right_camera["camera_matrix"], dtype=np.float64)
    left_dist = np.asarray(left_camera["distortion_coefficients"], dtype=np.float64).reshape(-1, 1)
    right_dist = np.asarray(right_camera["distortion_coefficients"], dtype=np.float64).reshape(-1, 1)
    rms_px, _k1, _d1, _k2, _d2, rotation, translation, essential, fundamental = cv2.stereoCalibrate(
        object_points,
        left_points,
        right_points,
        left_matrix,
        left_dist,
        right_matrix,
        right_dist,
        (image_size["width"], image_size["height"]),
        flags=cv2.CALIB_FIX_INTRINSIC,
    )
    r1, r2, p1, p2, q, roi1, roi2 = cv2.stereoRectify(
        left_matrix,
        left_dist,
        right_matrix,
        right_dist,
        (image_size["width"], image_size["height"]),
        rotation,
        translation,
    )
    accepted = bool(float(rms_px) <= max_rms_px)
    output.mkdir(parents=True, exist_ok=True)
    created_at = now_utc()
    left_package = read_json(left_mono / "package.json")
    right_package = read_json(right_mono / "package.json")
    dry_run = observations.get("dry_run") is True or left_package.get("dry_run") is True or right_package.get("dry_run") is True
    hardware_validated = (
        observations.get("hardware_validated") is True
        and left_package.get("hardware_validated") is True
        and right_package.get("hardware_validated") is True
    )
    stereo = {
        "schema_version": "calibration.stereo_extrinsics.v1",
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "rotation_left_to_right": matrix_to_list(rotation),
        "translation_left_to_right_m": vector_to_list(translation),
        "essential_matrix": matrix_to_list(essential),
        "fundamental_matrix": matrix_to_list(fundamental),
        "baseline_m": float(np.linalg.norm(translation)),
    }
    rectification = {
        "schema_version": "calibration.rectification.v1",
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "image_size": image_size,
        "r1": matrix_to_list(r1),
        "r2": matrix_to_list(r2),
        "p1": matrix_to_list(p1),
        "p2": matrix_to_list(p2),
        "q": matrix_to_list(q),
        "roi1": roi_to_payload(roi1),
        "roi2": roi_to_payload(roi2),
    }
    package = {
        "schema_version": "calibration.stereo.v1",
        "package_type": "stereo_camera_calibration",
        "camera_ids": [left_camera_id, right_camera_id],
        "created_at": created_at,
        "source_session": observations.get("session_path") or observations.get("session_id"),
        "accepted": accepted,
        "dry_run": dry_run,
        "hardware_validated": hardware_validated,
        "mono_sources": {left_camera_id: str(left_mono), right_camera_id: str(right_mono)},
        "target": observations.get("target", {}),
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
            "stereo_rms_reprojection_px": float(rms_px),
            "accepted_pair_count": len(matched_pairs),
            "total_pair_count": observations.get("total_pair_count", len(observations.get("pairs", []))),
            "max_rms_px": max_rms_px,
            "min_common_corner_count": min(int(pair["common_corner_count"]) for pair in matched_pairs),
        },
    }
    verification = {
        "schema_version": "calibration.stereo_verification.v1",
        "accepted": accepted,
        "dry_run": dry_run,
        "hardware_validated": hardware_validated,
        "checks": [
            {
                "name": "accepted_pair_count",
                "passed": len(matched_pairs) >= min_pairs,
                "value": len(matched_pairs),
                "minimum": min_pairs,
            },
            {
                "name": "stereo_rms_reprojection_px",
                "passed": float(rms_px) <= max_rms_px,
                "value": float(rms_px),
                "threshold": max_rms_px,
            },
            {
                "name": "baseline_m",
                "passed": float(np.linalg.norm(translation)) > 0,
                "value": float(np.linalg.norm(translation)),
                "minimum": 0,
            },
        ],
        "rectification": {
            "accepted": accepted,
            "epipolar_error_px": None,
        },
    }

    write_json(output / "package.json", package)
    write_json(output / "cam1.json", left_camera)
    write_json(output / "cam2.json", right_camera)
    write_json(output / "stereo.json", stereo)
    write_json(output / "rectification.json", rectification)
    write_json(output / "verification.json", verification)
    write_opencv_yaml(output / "calibration_opencv.yaml", "stereo", camera=left_camera, right_camera=right_camera, stereo=stereo)
    write_stereo_summary(output / "summary.md", package, verification)
    write_stereo_review_html(output / "review.html", package, verification)
    return {"accepted": accepted, "package": package, "stereo": stereo, "rectification": rectification, "verification": verification}


def matched_stereo_points(
    observations: dict[str, Any],
    left_camera_id: str,
    right_camera_id: str,
    min_common_corners: int,
) -> list[dict[str, Any]]:
    views = observations.get("views", [])
    left_by_index = {int(view["index"]): view for view in views if view.get("camera_id") == left_camera_id and view.get("accepted") is True}
    right_by_index = {int(view["index"]): view for view in views if view.get("camera_id") == right_camera_id and view.get("accepted") is True}
    matched = []
    for index in sorted(set(left_by_index) & set(right_by_index)):
        left = left_by_index[index]
        right = right_by_index[index]
        left_points_by_id = points_by_id(left)
        right_points_by_id = points_by_id(right)
        common_ids = sorted(set(left_points_by_id) & set(right_points_by_id))
        if len(common_ids) < min_common_corners:
            continue
        object_points = np.asarray([left_points_by_id[item]["object"] for item in common_ids], dtype=np.float32)
        left_image_points = np.asarray([left_points_by_id[item]["image"] for item in common_ids], dtype=np.float32)
        right_image_points = np.asarray([right_points_by_id[item]["image"] for item in common_ids], dtype=np.float32)
        matched.append(
            {
                "index": index,
                "common_corner_count": len(common_ids),
                "image_size": left["image_size"],
                "object_points": object_points,
                "left_image_points": left_image_points,
                "right_image_points": right_image_points,
            }
        )
    return matched


def points_by_id(view: dict[str, Any]) -> dict[int, dict[str, list[float]]]:
    ids = [int(item) for item in view["ids"]]
    image_points = view["image_points"]
    object_points = view["object_points"]
    return {
        ids[index]: {"image": image_points[index], "object": object_points[index]}
        for index in range(min(len(ids), len(image_points), len(object_points)))
    }


def common_pair_image_size(pairs: list[dict[str, Any]]) -> dict[str, int]:
    sizes = {
        (int(pair["image_size"]["width"]), int(pair["image_size"]["height"]))
        for pair in pairs
        if isinstance(pair.get("image_size"), dict)
    }
    if len(sizes) != 1:
        raise ValueError("accepted stereo pairs must have one common image size")
    width, height = next(iter(sizes))
    return {"width": width, "height": height}


def matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(matrix, dtype=np.float64).tolist()]


def vector_to_list(vector: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(vector, dtype=np.float64).reshape(-1).tolist()]


def roi_to_payload(roi: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = (int(value) for value in roi)
    return {"x": x, "y": y, "width": width, "height": height}


def write_stereo_summary(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    quality = package["quality"]
    lines = [
        "# Stereo Calibration Package",
        "",
        f"- camera_ids: {', '.join(package['camera_ids'])}",
        f"- created_at: {package['created_at']}",
        f"- accepted: {package['accepted']}",
        f"- dry_run: {package['dry_run']}",
        f"- hardware_validated: {package['hardware_validated']}",
        f"- source_session: {package['source_session']}",
        f"- stereo_rms_reprojection_px: {quality['stereo_rms_reprojection_px']}",
        f"- accepted_pair_count: {quality['accepted_pair_count']} / {quality['total_pair_count']}",
        "",
        "## Checks",
        "",
    ]
    for check in verification["checks"]:
        lines.append(f"- {check['name']}: passed={check['passed']} value={check['value']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_stereo_review_html(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stereo Calibration Package</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #111827; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Stereo Calibration Package</h1>
  <p><code>camera_ids</code>: {', '.join(package['camera_ids'])}</p>
  <p><code>accepted</code>: {package['accepted']}</p>
  <p><code>dry_run</code>: {package['dry_run']}</p>
  <p><code>hardware_validated</code>: {package['hardware_validated']}</p>
  <p><code>stereo_rms_reprojection_px</code>: {package['quality']['stereo_rms_reprojection_px']}</p>
  <p><code>verification_accepted</code>: {verification['accepted']}</p>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
