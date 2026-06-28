from __future__ import annotations

from pathlib import Path
from typing import Any

from tennisbot_calibration.io import write_json

CREATED_AT = "2026-06-29T00:00:00Z"
IMAGE_SIZE = {"width": 1920, "height": 1080}
TARGET = {
    "type": "charuco",
    "profile": "dfoptix_charuco_15mm",
    "square_size_m": 0.015,
    "marker_size_m": 0.011,
}


def write_mono_dry_run(camera_id: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    camera = camera_payload(camera_id)
    package = {
        "schema_version": "calibration.mono.v1",
        "package_type": "mono_camera_calibration",
        "camera_id": camera_id,
        "created_at": CREATED_AT,
        "source_session": f"dry-run/non-hardware/{camera_id}_session",
        "accepted": True,
        "dry_run": True,
        "hardware_validated": False,
        "target": TARGET,
        "image_size": IMAGE_SIZE,
        "files": {
            "camera": "camera.json",
            "opencv_yaml": "calibration_opencv.yaml",
            "verification": "verification.json",
            "summary": "summary.md",
            "review_html": "review.html",
        },
        "quality": {
            "accepted": True,
            "rms_reprojection_px": 0.35,
            "accepted_view_count": 25,
            "total_view_count": 30,
        },
    }
    verification = {
        "schema_version": "calibration.verification.v1",
        "accepted": True,
        "dry_run": True,
        "hardware_validated": False,
        "checks": [
            {
                "name": "rms_reprojection_px",
                "passed": True,
                "value": 0.35,
                "threshold": 0.5,
            }
        ],
        "coverage": {
            "center": "dry-run-good",
            "edges": "dry-run-good",
            "corners": "dry-run-acceptable",
        },
    }

    write_json(output / "package.json", package)
    write_json(output / "camera.json", camera)
    write_json(output / "verification.json", verification)
    write_opencv_yaml(output / "calibration_opencv.yaml", "mono", camera=camera)
    write_summary(output / "summary.md", "Mono Calibration Dry Run", package, verification)
    write_review_html(output / "review.html", "Mono Calibration Dry Run", package, verification)
    return package


def write_stereo_dry_run(left_camera_id: str, right_camera_id: str, output: Path) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    left_camera = camera_payload(left_camera_id)
    right_camera = camera_payload(right_camera_id)
    stereo = stereo_payload(left_camera_id, right_camera_id)
    rectification = rectification_payload(left_camera_id, right_camera_id)
    package = {
        "schema_version": "calibration.stereo.v1",
        "package_type": "stereo_camera_calibration",
        "camera_ids": [left_camera_id, right_camera_id],
        "created_at": CREATED_AT,
        "source_session": f"dry-run/non-hardware/stereo_{left_camera_id}_{right_camera_id}_session",
        "accepted": True,
        "dry_run": True,
        "hardware_validated": False,
        "mono_sources": {
            left_camera_id: f"artifacts/calibration/{left_camera_id}",
            right_camera_id: f"artifacts/calibration/{right_camera_id}",
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
            "accepted": True,
            "stereo_rms_reprojection_px": 0.42,
            "accepted_pair_count": 28,
            "total_pair_count": 32,
        },
    }
    verification = {
        "schema_version": "calibration.stereo_verification.v1",
        "accepted": True,
        "dry_run": True,
        "hardware_validated": False,
        "checks": [
            {
                "name": "stereo_rms_reprojection_px",
                "passed": True,
                "value": 0.42,
                "threshold": 0.75,
            },
            {
                "name": "baseline_m",
                "passed": True,
                "value": 0.12,
                "minimum": 0.05,
                "maximum": 0.5,
            },
        ],
        "rectification": {
            "epipolar_error_px": 0.3,
            "accepted": True,
        },
    }

    write_json(output / "package.json", package)
    write_json(output / "cam1.json", left_camera)
    write_json(output / "cam2.json", right_camera)
    write_json(output / "stereo.json", stereo)
    write_json(output / "rectification.json", rectification)
    write_json(output / "verification.json", verification)
    write_opencv_yaml(
        output / "calibration_opencv.yaml",
        "stereo",
        camera=left_camera,
        right_camera=right_camera,
        stereo=stereo,
    )
    write_summary(output / "summary.md", "Stereo Calibration Dry Run", package, verification)
    write_review_html(output / "review.html", "Stereo Calibration Dry Run", package, verification)
    return package


def camera_payload(camera_id: str) -> dict[str, Any]:
    return {
        "schema_version": "calibration.camera_intrinsics.v1",
        "camera_id": camera_id,
        "image_size": IMAGE_SIZE,
        "camera_matrix": [
            [1200.0, 0.0, 960.0],
            [0.0, 1200.0, 540.0],
            [0.0, 0.0, 1.0],
        ],
        "distortion_model": "opencv_rational",
        "distortion_coefficients": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "new_camera_matrix": [
            [1180.0, 0.0, 960.0],
            [0.0, 1180.0, 540.0],
            [0.0, 0.0, 1.0],
        ],
        "roi": {"x": 0, "y": 0, "width": 1920, "height": 1080},
    }


def stereo_payload(left_camera_id: str, right_camera_id: str) -> dict[str, Any]:
    return {
        "schema_version": "calibration.stereo_extrinsics.v1",
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "rotation_left_to_right": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "translation_left_to_right_m": [0.12, 0.0, 0.0],
        "essential_matrix": [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, -0.12],
            [0.0, 0.12, 0.0],
        ],
        "fundamental_matrix": [
            [0.0, 0.0, 0.0],
            [0.0, 0.0, -0.0001],
            [0.0, 0.0001, 0.0],
        ],
        "baseline_m": 0.12,
    }


def rectification_payload(left_camera_id: str, right_camera_id: str) -> dict[str, Any]:
    return {
        "schema_version": "calibration.rectification.v1",
        "left_camera_id": left_camera_id,
        "right_camera_id": right_camera_id,
        "image_size": IMAGE_SIZE,
        "r1": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "r2": [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ],
        "p1": [
            [1200.0, 0.0, 960.0, 0.0],
            [0.0, 1200.0, 540.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        "p2": [
            [1200.0, 0.0, 960.0, -144.0],
            [0.0, 1200.0, 540.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
        "q": [
            [1.0, 0.0, 0.0, -960.0],
            [0.0, 1.0, 0.0, -540.0],
            [0.0, 0.0, 0.0, 1200.0],
            [0.0, 0.0, 8.3333333333, 0.0],
        ],
    }


def write_summary(path: Path, title: str, package: dict[str, Any], verification: dict[str, Any]) -> None:
    files = package.get("files", {})
    file_names = files.values() if isinstance(files, dict) else []
    lines = [
        f"# {title}",
        "",
        "This package is dry-run/non-hardware evidence only.",
        "It does not prove physical camera capture, OpenCV solve quality, or runtime catch-loop readiness.",
        "",
        f"- package_type: {package['package_type']}",
        f"- created_at: {package['created_at']}",
        f"- accepted: {verification['accepted']}",
        "- dry_run: True",
        "- hardware_validated: False",
        "",
        "## Files",
        "",
    ]
    lines.extend(f"- {name}" for name in file_names)
    lines.extend(
        [
            "",
            "## Verification",
            "",
            f"- accepted: {verification['accepted']}",
            "- evidence_type: deterministic fixture output",
            "- next_gate: real camera capture and calibration solve",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_html(path: Path, title: str, package: dict[str, Any], verification: dict[str, Any]) -> None:
    files = package.get("files", {})
    file_names = files.values() if isinstance(files, dict) else []
    items = "\n".join(f"<li>{name}</li>" for name in file_names)
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{title}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; }}
    .warning {{ border: 2px solid #b45309; padding: 1rem; background: #fffbeb; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <section class="warning">
    <strong>Dry-run/non-hardware evidence only.</strong>
    This output did not open physical cameras and must not be used as real calibration validation.
  </section>
  <p><code>accepted</code>: {verification['accepted']}</p>
  <p><code>hardware_validated</code>: False</p>
  <h2>Package Files</h2>
  <ul>
    {items}
  </ul>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def write_opencv_yaml(
    path: Path,
    topology: str,
    *,
    camera: dict[str, Any],
    right_camera: dict[str, Any] | None = None,
    stereo: dict[str, Any] | None = None,
) -> None:
    lines = [
        "%YAML:1.0",
        "---",
        "schema_version: calibration.opencv.v1",
        f"topology: {topology}",
    ]
    if topology == "mono":
        lines.extend(
            [
                f"camera_id: {camera['camera_id']}",
                f"camera_matrix: {camera['camera_matrix']}",
                f"dist_coeffs: {camera['distortion_coefficients']}",
            ]
        )
    else:
        assert right_camera is not None
        assert stereo is not None
        lines.extend(
            [
                f"left_camera_id: {camera['camera_id']}",
                f"right_camera_id: {right_camera['camera_id']}",
                f"left_camera_matrix: {camera['camera_matrix']}",
                f"right_camera_matrix: {right_camera['camera_matrix']}",
                f"rotation: {stereo['rotation_left_to_right']}",
                f"translation: {stereo['translation_left_to_right_m']}",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
