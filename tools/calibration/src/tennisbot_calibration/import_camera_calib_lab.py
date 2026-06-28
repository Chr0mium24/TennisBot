from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.artifacts import TARGET
from tennisbot_calibration.io import read_json, write_json


QUALITY_WARNING_LIMITS = {
    "stereo_rms_px": 2.0,
    "epipolar_rms_px": 2.0,
    "rectification_y_p95_px": 2.0,
}


def import_camera_calib_lab_package(
    *,
    cam1_path: Path,
    cam2_path: Path,
    stereo_path: Path,
    output: Path,
    left_camera_id: str,
    right_camera_id: str,
    source_session: str | None = None,
) -> dict[str, Any]:
    cam1_source = read_json(cam1_path)
    cam2_source = read_json(cam2_path)
    stereo_source = read_json(stereo_path)

    require_topology(cam1_source, "mono", cam1_path)
    require_topology(cam2_source, "mono", cam2_path)
    require_topology(stereo_source, "stereo", stereo_path)

    left_camera = camera_artifact(cam1_source, left_camera_id)
    right_camera = camera_artifact(cam2_source, right_camera_id)
    stereo = stereo_artifact(stereo_source, left_camera, right_camera, left_camera_id, right_camera_id)
    rectification = rectification_artifact(stereo_source, left_camera, right_camera, stereo)
    verification = verification_artifact(stereo_source)
    package = package_artifact(
        cam1_source,
        cam2_source,
        stereo_source,
        left_camera_id,
        right_camera_id,
        source_session or str(stereo_path),
    )

    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "package.json", package)
    write_json(output / "cam1.json", left_camera)
    write_json(output / "cam2.json", right_camera)
    write_json(output / "stereo.json", stereo)
    write_json(output / "rectification.json", rectification)
    write_json(output / "verification.json", verification)
    write_opencv_yaml(output / "calibration_opencv.yaml", left_camera, right_camera, stereo, rectification)
    write_summary(output / "summary.md", package, verification)
    write_review_html(output / "review.html", package, verification)
    return package


def require_topology(source: dict[str, Any], expected: str, path: Path) -> None:
    topology = source.get("topology")
    if topology != expected:
        raise ValueError(f"{path} topology must be {expected!r}, got {topology!r}")
    if source.get("status") != "ready":
        raise ValueError(f"{path} status must be 'ready', got {source.get('status')!r}")


def camera_artifact(source: dict[str, Any], camera_id: str) -> dict[str, Any]:
    image_size = image_size_payload(source)
    image_size_tuple = (image_size["width"], image_size["height"])
    camera_matrix = as_matrix(source.get("camera_matrix"), 3, 3, "camera_matrix")
    dist_coeffs = as_float_list(source.get("dist_coeffs"), "dist_coeffs")

    new_camera_matrix, roi = cv2.getOptimalNewCameraMatrix(
        np.asarray(camera_matrix, dtype=np.float64),
        np.asarray(dist_coeffs, dtype=np.float64),
        image_size_tuple,
        0,
        image_size_tuple,
    )

    return {
        "schema_version": "calibration.camera_intrinsics.v1",
        "camera_id": camera_id,
        "image_size": image_size,
        "camera_matrix": to_nested_float_list(camera_matrix),
        "distortion_model": distortion_model(dist_coeffs),
        "distortion_coefficients": to_float_list(dist_coeffs),
        "new_camera_matrix": to_nested_float_list(new_camera_matrix),
        "roi": roi_payload(roi),
        "source_result_id": source.get("result_id"),
        "source_method_id": source.get("method_id"),
        "source_metrics": source.get("metrics", {}),
    }


def stereo_artifact(
    source: dict[str, Any],
    left_camera: dict[str, Any],
    right_camera: dict[str, Any],
    left_camera_id: str,
    right_camera_id: str,
) -> dict[str, Any]:
    rotation = np.asarray(as_matrix(source.get("rotation"), 3, 3, "rotation"), dtype=np.float64)
    translation = np.asarray(as_vector(source.get("translation"), 3, "translation"), dtype=np.float64)
    left_k = np.asarray(left_camera["camera_matrix"], dtype=np.float64)
    right_k = np.asarray(right_camera["camera_matrix"], dtype=np.float64)
    essential = skew(translation) @ rotation
    fundamental = np.linalg.inv(right_k).T @ essential @ np.linalg.inv(left_k)
    metrics = source.get("metrics", {})
    baseline_m = float(metrics.get("baseline_m") or np.linalg.norm(translation))

    return {
        "schema_version": "calibration.stereo_extrinsics.v1",
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "rotation_left_to_right": to_nested_float_list(rotation),
        "translation_left_to_right_m": to_float_list(translation),
        "essential_matrix": to_nested_float_list(essential),
        "fundamental_matrix": to_nested_float_list(fundamental),
        "baseline_m": baseline_m,
        "source_result_id": source.get("result_id"),
        "source_method_id": source.get("method_id"),
        "source_metrics": metrics,
    }


def rectification_artifact(
    source: dict[str, Any],
    left_camera: dict[str, Any],
    right_camera: dict[str, Any],
    stereo: dict[str, Any],
) -> dict[str, Any]:
    image_size = image_size_payload(source)
    image_size_tuple = (image_size["width"], image_size["height"])
    left_k = np.asarray(left_camera["camera_matrix"], dtype=np.float64)
    left_d = np.asarray(left_camera["distortion_coefficients"], dtype=np.float64)
    right_k = np.asarray(right_camera["camera_matrix"], dtype=np.float64)
    right_d = np.asarray(right_camera["distortion_coefficients"], dtype=np.float64)
    rotation = np.asarray(stereo["rotation_left_to_right"], dtype=np.float64)
    translation = np.asarray(stereo["translation_left_to_right_m"], dtype=np.float64)

    r1, r2, p1, p2, q, left_roi, right_roi = cv2.stereoRectify(
        left_k,
        left_d,
        right_k,
        right_d,
        image_size_tuple,
        rotation,
        translation,
        flags=cv2.CALIB_ZERO_DISPARITY,
        alpha=0,
    )

    return {
        "schema_version": "calibration.rectification.v1",
        "left_camera_id": stereo["left_camera_id"],
        "right_camera_id": stereo["right_camera_id"],
        "image_size": image_size,
        "r1": to_nested_float_list(r1),
        "r2": to_nested_float_list(r2),
        "p1": to_nested_float_list(p1),
        "p2": to_nested_float_list(p2),
        "q": to_nested_float_list(q),
        "left_roi": roi_payload(left_roi),
        "right_roi": roi_payload(right_roi),
    }


def package_artifact(
    cam1_source: dict[str, Any],
    cam2_source: dict[str, Any],
    stereo_source: dict[str, Any],
    left_camera_id: str,
    right_camera_id: str,
    source_session: str,
) -> dict[str, Any]:
    stereo_metrics = stereo_source.get("metrics", {})
    warnings = quality_warnings(stereo_metrics)
    accepted = source_validation_failures(stereo_source) == []
    return {
        "schema_version": "calibration.stereo.v1",
        "package_type": "stereo_camera_calibration",
        "camera_ids": [left_camera_id, right_camera_id],
        "created_at": str(stereo_source.get("created_at") or now_utc()),
        "source_session": source_session,
        "accepted": accepted,
        "dry_run": False,
        "hardware_validated": True,
        "runtime_quality_warning": bool(warnings),
        "mono_sources": {
            left_camera_id: str(cam1_source.get("result_id") or "CameraCalibLab/cam1_mono"),
            right_camera_id: str(cam2_source.get("result_id") or "CameraCalibLab/cam2_mono"),
        },
        "target": TARGET,
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
            "stereo_rms_reprojection_px": metric_float(stereo_metrics, "stereo_rms_px"),
            "epipolar_rms_px": metric_float(stereo_metrics, "epipolar_rms_px"),
            "rectification_y_p95_px": metric_float(stereo_metrics, "rectification_y_p95_px"),
            "accepted_pair_count": metric_int(stereo_metrics, "accepted_pairs"),
            "matched_point_count_min": metric_int(stereo_metrics, "matched_point_count_min"),
            "baseline_m": metric_float(stereo_metrics, "baseline_m"),
            "warnings": warnings,
        },
    }


def verification_artifact(source: dict[str, Any]) -> dict[str, Any]:
    metrics = source.get("metrics", {})
    validation = source.get("validation", {})
    failures = source_validation_failures(source)
    warnings = quality_warnings(metrics)
    accepted = source.get("status") == "ready" and failures == []
    return {
        "schema_version": "calibration.stereo_verification.v1",
        "accepted": accepted,
        "dry_run": False,
        "hardware_validated": True,
        "checks": [
            {
                "name": "source_status_ready",
                "passed": source.get("status") == "ready",
                "value": source.get("status"),
            },
            {
                "name": "source_validation_failures_empty",
                "passed": failures == [],
                "value": failures,
            },
            metric_check(metrics, "stereo_rms_px"),
            metric_check(metrics, "epipolar_rms_px"),
            metric_check(metrics, "rectification_y_p95_px"),
            metric_check(metrics, "baseline_m"),
        ],
        "rectification": {
            "accepted": accepted,
            "epipolar_error_px": metric_float(metrics, "epipolar_rms_px"),
            "rectification_y_p95_px": metric_float(metrics, "rectification_y_p95_px"),
        },
        "warnings": warnings,
        "source_validation_id": validation.get("validation_id") if isinstance(validation, dict) else None,
    }


def metric_check(metrics: dict[str, Any], name: str) -> dict[str, Any]:
    limit = QUALITY_WARNING_LIMITS.get(name)
    value = metric_float(metrics, name)
    check = {
        "name": name,
        "passed": value is not None,
        "value": value,
    }
    if limit is not None:
        check["warning_threshold"] = limit
        check["warning"] = value is not None and value > limit
    return check


def quality_warnings(metrics: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for name, limit in QUALITY_WARNING_LIMITS.items():
        value = metric_float(metrics, name)
        if value is not None and value > limit:
            warnings.append(f"{name}={value:.3f} exceeds runtime-quality review threshold {limit:.3f}")
    return warnings


def source_validation_failures(source: dict[str, Any]) -> list[Any]:
    validation = source.get("validation", {})
    if not isinstance(validation, dict):
        return ["missing validation block"]
    failures = validation.get("failures", [])
    if not isinstance(failures, list):
        return ["validation failures field is not a list"]
    return failures


def image_size_payload(source: dict[str, Any]) -> dict[str, int]:
    raw = source.get("image_size")
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError("image_size must be [width, height]")
    width = int(raw[0])
    height = int(raw[1])
    if width <= 0 or height <= 0:
        raise ValueError("image_size values must be positive")
    return {"width": width, "height": height}


def as_matrix(value: object, rows: int, cols: int, name: str) -> list[list[float]]:
    if not isinstance(value, list) or len(value) != rows:
        raise ValueError(f"{name} must be {rows}x{cols}")
    matrix = []
    for row in value:
        if not isinstance(row, list) or len(row) != cols:
            raise ValueError(f"{name} must be {rows}x{cols}")
        matrix.append([float(item) for item in row])
    return matrix


def as_vector(value: object, length: int, name: str) -> list[float]:
    if not isinstance(value, list) or len(value) != length:
        raise ValueError(f"{name} must be a length-{length} vector")
    return [float(item) for item in value]


def as_float_list(value: object, name: str) -> list[float]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{name} must be a non-empty numeric list")
    return [float(item) for item in value]


def distortion_model(coefficients: list[float]) -> str:
    if len(coefficients) >= 8:
        return "opencv_rational"
    return "opencv_standard"


def metric_float(metrics: dict[str, Any], name: str) -> float | None:
    value = metrics.get(name)
    if value is None:
        return None
    return float(value)


def metric_int(metrics: dict[str, Any], name: str) -> int | None:
    value = metrics.get(name)
    if value is None:
        return None
    return int(value)


def skew(vector: np.ndarray) -> np.ndarray:
    tx, ty, tz = vector.tolist()
    return np.asarray(
        [
            [0.0, -tz, ty],
            [tz, 0.0, -tx],
            [-ty, tx, 0.0],
        ],
        dtype=np.float64,
    )


def roi_payload(roi: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = [int(value) for value in roi]
    return {"x": x, "y": y, "width": width, "height": height}


def to_nested_float_list(value: object) -> list[list[float]]:
    array = np.asarray(value, dtype=np.float64)
    return [[float(item) for item in row] for row in array.tolist()]


def to_float_list(value: object) -> list[float]:
    array = np.asarray(value, dtype=np.float64).reshape(-1)
    return [float(item) for item in array.tolist()]


def now_utc() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def write_opencv_yaml(
    path: Path,
    left_camera: dict[str, Any],
    right_camera: dict[str, Any],
    stereo: dict[str, Any],
    rectification: dict[str, Any],
) -> None:
    lines = [
        "%YAML:1.0",
        "---",
        "schema_version: calibration.opencv.v1",
        "topology: stereo",
        f"left_camera_id: {left_camera['camera_id']}",
        f"right_camera_id: {right_camera['camera_id']}",
        f"left_camera_matrix: {left_camera['camera_matrix']}",
        f"left_dist_coeffs: {left_camera['distortion_coefficients']}",
        f"right_camera_matrix: {right_camera['camera_matrix']}",
        f"right_dist_coeffs: {right_camera['distortion_coefficients']}",
        f"rotation: {stereo['rotation_left_to_right']}",
        f"translation: {stereo['translation_left_to_right_m']}",
        f"rectification_r1: {rectification['r1']}",
        f"rectification_r2: {rectification['r2']}",
        f"projection_p1: {rectification['p1']}",
        f"projection_p2: {rectification['p2']}",
        f"disparity_q: {rectification['q']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    quality = package["quality"]
    warnings = quality.get("warnings") or []
    lines = [
        "# Stereo Calibration CameraCalibLab Import",
        "",
        "Imported from CameraCalibLab calibration JSON into the TennisBot runtime artifact contract.",
        "",
        f"- package_type: {package['package_type']}",
        f"- created_at: {package['created_at']}",
        f"- accepted: {verification['accepted']}",
        "- dry_run: False",
        "- hardware_validated: True",
        f"- runtime_quality_warning: {package['runtime_quality_warning']}",
        f"- cameras: {', '.join(package['camera_ids'])}",
        f"- baseline_m: {quality.get('baseline_m')}",
        f"- accepted_pair_count: {quality.get('accepted_pair_count')}",
        f"- stereo_rms_reprojection_px: {quality.get('stereo_rms_reprojection_px')}",
        f"- epipolar_rms_px: {quality.get('epipolar_rms_px')}",
        f"- rectification_y_p95_px: {quality.get('rectification_y_p95_px')}",
        "",
        "## Quality Notes",
        "",
    ]
    if warnings:
        lines.append("The imported source is real hardware output, but current stereo quality metrics require review:")
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("- Re-run mono and stereo calibration before treating 3D prediction as physically accurate.")
    else:
        lines.append("No runtime-quality warning threshold was exceeded.")
    lines.extend(
        [
            "",
            "## Files",
            "",
        ]
    )
    lines.extend(f"- {name}" for name in package["files"].values())
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_html(path: Path, package: dict[str, Any], verification: dict[str, Any]) -> None:
    files = "\n".join(f"<li>{name}</li>" for name in package["files"].values())
    warnings = verification.get("warnings") or []
    warnings_html = "\n".join(f"<li>{warning}</li>" for warning in warnings) or "<li>No warnings.</li>"
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Stereo Calibration CameraCalibLab Import</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #111827; }}
    .warning {{ border: 2px solid #b45309; padding: 1rem; background: #fffbeb; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Stereo Calibration CameraCalibLab Import</h1>
  <section class="warning">
    <strong>Quality review required.</strong>
    This artifact was imported from real calibration output, but runtime 3D accuracy still depends on live-camera validation.
  </section>
  <p><code>accepted</code>: {verification['accepted']}</p>
  <p><code>dry_run</code>: False</p>
  <p><code>hardware_validated</code>: True</p>
  <h2>Warnings</h2>
  <ul>
    {warnings_html}
  </ul>
  <h2>Package Files</h2>
  <ul>
    {files}
  </ul>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")
