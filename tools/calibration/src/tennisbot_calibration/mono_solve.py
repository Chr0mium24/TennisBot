from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.artifacts import write_opencv_yaml
from tennisbot_calibration.capture_sessions import now_utc
from tennisbot_calibration.io import write_json


def solve_mono_calibration(
    *,
    observations_path: Path,
    output: Path,
    camera_id: str | None = None,
    min_views: int = 8,
    max_rms_px: float = 1.0,
) -> dict[str, Any]:
    if min_views <= 0:
        raise ValueError("min_views must be positive")
    if max_rms_px <= 0:
        raise ValueError("max_rms_px must be positive")
    observations = json.loads(observations_path.read_text(encoding="utf-8"))
    selected_camera_id = camera_id or infer_single_camera_id(observations)
    views = accepted_views_for_camera(observations, selected_camera_id)
    if len(views) < min_views:
        raise RuntimeError(f"accepted view count {len(views)} is below required minimum {min_views}")

    image_size = common_image_size(views)
    object_points = [np.asarray(view["object_points"], dtype=np.float32).reshape(-1, 3) for view in views]
    image_points = [np.asarray(view["image_points"], dtype=np.float32).reshape(-1, 2) for view in views]
    rms_px, camera_matrix, dist_coeffs, _rvecs, _tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        (image_size["width"], image_size["height"]),
        None,
        None,
    )
    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
        camera_matrix,
        dist_coeffs,
        (image_size["width"], image_size["height"]),
        0,
    )
    accepted = bool(float(rms_px) <= max_rms_px)
    output.mkdir(parents=True, exist_ok=True)
    created_at = now_utc()
    dry_run = observations.get("dry_run") is True
    hardware_validated = observations.get("hardware_validated") is True
    camera = {
        "schema_version": "calibration.camera_intrinsics.v1",
        "camera_id": selected_camera_id,
        "image_size": image_size,
        "camera_matrix": matrix_to_list(camera_matrix),
        "distortion_model": distortion_model_name(dist_coeffs),
        "distortion_coefficients": vector_to_list(dist_coeffs),
        "new_camera_matrix": matrix_to_list(new_camera_matrix),
        "roi": roi_to_payload(roi),
    }
    package = {
        "schema_version": "calibration.mono.v1",
        "package_type": "mono_camera_calibration",
        "camera_id": selected_camera_id,
        "created_at": created_at,
        "source_session": observations.get("session_path") or observations.get("session_id"),
        "accepted": accepted,
        "dry_run": dry_run,
        "hardware_validated": hardware_validated,
        "target": observations.get("target", {}),
        "image_size": image_size,
        "files": {
            "camera": "camera.json",
            "opencv_yaml": "calibration_opencv.yaml",
            "verification": "verification.json",
            "summary": "summary.md",
            "review_html": "review.html",
        },
        "quality": {
            "accepted": accepted,
            "rms_reprojection_px": float(rms_px),
            "accepted_view_count": len(views),
            "total_view_count": observations.get("total_view_count", len(observations.get("views", []))),
            "max_rms_px": max_rms_px,
        },
    }
    verification = {
        "schema_version": "calibration.verification.v1",
        "accepted": accepted,
        "dry_run": dry_run,
        "hardware_validated": hardware_validated,
        "checks": [
            {
                "name": "accepted_view_count",
                "passed": len(views) >= min_views,
                "value": len(views),
                "minimum": min_views,
            },
            {
                "name": "rms_reprojection_px",
                "passed": float(rms_px) <= max_rms_px,
                "value": float(rms_px),
                "threshold": max_rms_px,
            },
        ],
        "coverage": coverage_from_views(views),
    }

    write_json(output / "package.json", package)
    write_json(output / "camera.json", camera)
    write_json(output / "verification.json", verification)
    write_opencv_yaml(output / "calibration_opencv.yaml", "mono", camera=camera)
    write_mono_summary(output / "summary.md", package, verification)
    write_mono_review_html(output / "review.html", package, verification)
    return {"accepted": accepted, "package": package, "camera": camera, "verification": verification}


def infer_single_camera_id(observations: dict[str, Any]) -> str:
    camera_ids = sorted({str(view["camera_id"]) for view in observations.get("views", []) if view.get("accepted") is True})
    if len(camera_ids) != 1:
        raise ValueError("--camera-id is required when observations contain zero or multiple accepted cameras")
    return camera_ids[0]


def accepted_views_for_camera(observations: dict[str, Any], camera_id: str) -> list[dict[str, Any]]:
    return [
        view
        for view in observations.get("views", [])
        if view.get("accepted") is True and str(view.get("camera_id")) == camera_id
    ]


def common_image_size(views: list[dict[str, Any]]) -> dict[str, int]:
    sizes = {
        (int(view["image_size"]["width"]), int(view["image_size"]["height"]))
        for view in views
        if isinstance(view.get("image_size"), dict)
    }
    if len(sizes) != 1:
        raise ValueError("accepted views must have one common image size")
    width, height = next(iter(sizes))
    return {"width": width, "height": height}


def matrix_to_list(matrix: np.ndarray) -> list[list[float]]:
    return [[float(value) for value in row] for row in np.asarray(matrix, dtype=np.float64).tolist()]


def vector_to_list(vector: np.ndarray) -> list[float]:
    return [float(value) for value in np.asarray(vector, dtype=np.float64).reshape(-1).tolist()]


def distortion_model_name(dist_coeffs: np.ndarray) -> str:
    return "opencv_rational" if int(np.asarray(dist_coeffs).size) > 5 else "opencv_brown_conrady"


def roi_to_payload(roi: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = (int(value) for value in roi)
    return {"x": x, "y": y, "width": width, "height": height}


def coverage_from_views(views: list[dict[str, Any]]) -> dict[str, object]:
    corner_counts = [int(view.get("corner_count", 0)) for view in views]
    return {
        "accepted_view_count": len(views),
        "corner_count_min": min(corner_counts) if corner_counts else 0,
        "corner_count_max": max(corner_counts) if corner_counts else 0,
    }


def write_mono_summary(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    quality = package["quality"]
    lines = [
        "# Mono Calibration Package",
        "",
        f"- camera_id: {package['camera_id']}",
        f"- created_at: {package['created_at']}",
        f"- accepted: {package['accepted']}",
        f"- dry_run: {package['dry_run']}",
        f"- hardware_validated: {package['hardware_validated']}",
        f"- source_session: {package['source_session']}",
        f"- image_size: {package['image_size']['width']}x{package['image_size']['height']}",
        f"- rms_reprojection_px: {quality['rms_reprojection_px']}",
        f"- accepted_view_count: {quality['accepted_view_count']} / {quality['total_view_count']}",
        "",
        "## Checks",
        "",
    ]
    for check in verification["checks"]:
        lines.append(f"- {check['name']}: passed={check['passed']} value={check['value']}")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_mono_review_html(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Mono Calibration Package</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #111827; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Mono Calibration Package</h1>
  <p><code>camera_id</code>: {package['camera_id']}</p>
  <p><code>accepted</code>: {package['accepted']}</p>
  <p><code>dry_run</code>: {package['dry_run']}</p>
  <p><code>hardware_validated</code>: {package['hardware_validated']}</p>
  <p><code>rms_reprojection_px</code>: {package['quality']['rms_reprojection_px']}</p>
  <p><code>verification_accepted</code>: {verification['accepted']}</p>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
