from __future__ import annotations

from pathlib import Path
from typing import Any

from tennisbot_calibration.io import read_json

MONO_REQUIRED_FILES = {
    "package.json",
    "camera.json",
    "verification.json",
    "calibration_opencv.yaml",
    "summary.md",
}
STEREO_REQUIRED_FILES = {
    "package.json",
    "cam1.json",
    "cam2.json",
    "stereo.json",
    "rectification.json",
    "verification.json",
    "calibration_opencv.yaml",
    "summary.md",
}


def verify_package(package_dir: Path) -> dict[str, Any]:
    package_path = package_dir / "package.json"
    if not package_path.is_file():
        return failure(package_dir, "missing package.json", ["package.json"])

    try:
        package = read_json(package_path)
    except (OSError, ValueError) as exc:
        return failure(package_dir, f"invalid package.json: {exc}", [])

    package_type = package.get("package_type")
    if package_type == "mono_camera_calibration":
        return verify_mono_package(package_dir, package)
    if package_type == "stereo_camera_calibration":
        return verify_stereo_package(package_dir, package)
    return failure(package_dir, f"unsupported package_type: {package_type}", [])


def verify_mono_package(package_dir: Path, package: dict[str, Any]) -> dict[str, Any]:
    missing = missing_files(package_dir, MONO_REQUIRED_FILES | files_declared_by(package))
    details: list[str] = []
    accepted = not missing
    if not package_accepted(package):
        accepted = False
        details.append("package accepted flag is false")
    verification = load_optional_json(package_dir / "verification.json")
    if verification is None:
        accepted = False
    elif verification.get("accepted") is not True:
        accepted = False
        details.append("verification accepted flag is false")
    camera = load_optional_json(package_dir / "camera.json")
    if camera is None:
        accepted = False
    elif camera.get("camera_id") != package.get("camera_id"):
        accepted = False
        details.append("camera_id mismatch")
    return result(package_dir, "mono", accepted, missing, details, package)


def verify_stereo_package(package_dir: Path, package: dict[str, Any]) -> dict[str, Any]:
    missing = missing_files(package_dir, STEREO_REQUIRED_FILES | files_declared_by(package))
    details: list[str] = []
    accepted = not missing
    if not package_accepted(package):
        accepted = False
        details.append("package accepted flag is false")
    verification = load_optional_json(package_dir / "verification.json")
    if verification is None:
        accepted = False
    elif verification.get("accepted") is not True:
        accepted = False
        details.append("verification accepted flag is false")
    else:
        rectification_verification = verification.get("rectification")
        if not isinstance(rectification_verification, dict):
            accepted = False
            details.append("verification rectification block is missing")
        elif rectification_verification.get("accepted") is not True:
            accepted = False
            details.append("verification rectification accepted flag is false")

    camera_ids = package.get("camera_ids")
    if not isinstance(camera_ids, list) or len(camera_ids) != 2:
        accepted = False
        details.append("camera_ids must contain left and right IDs")
        left_id = None
        right_id = None
    else:
        left_id = str(camera_ids[0])
        right_id = str(camera_ids[1])

    cam1 = load_optional_json(package_dir / "cam1.json")
    cam2 = load_optional_json(package_dir / "cam2.json")
    stereo = load_optional_json(package_dir / "stereo.json")
    rectification = load_optional_json(package_dir / "rectification.json")
    if left_id and cam1 and cam1.get("camera_id") != left_id:
        accepted = False
        details.append("cam1.json camera_id does not match package left camera")
    if right_id and cam2 and cam2.get("camera_id") != right_id:
        accepted = False
        details.append("cam2.json camera_id does not match package right camera")
    for payload_name, payload in (("stereo.json", stereo), ("rectification.json", rectification)):
        if payload is None:
            accepted = False
            continue
        if left_id and payload.get("left_camera_id") != left_id:
            accepted = False
            details.append(f"{payload_name} left_camera_id mismatch")
        if right_id and payload.get("right_camera_id") != right_id:
            accepted = False
            details.append(f"{payload_name} right_camera_id mismatch")
    if rectification is not None:
        for name, rows, cols in (("r1", 3, 3), ("r2", 3, 3), ("p1", 3, 4), ("p2", 3, 4), ("q", 4, 4)):
            if not is_matrix(rectification.get(name), rows, cols):
                accepted = False
                details.append(f"rectification {name} is not a {rows}x{cols} row-major matrix")
    return result(package_dir, "stereo", accepted, missing, details, package)


def files_declared_by(package: dict[str, Any]) -> set[str]:
    files = package.get("files")
    if isinstance(files, dict):
        return {str(value) for value in files.values()}
    if isinstance(files, list):
        return {str(value) for value in files}
    return set()


def missing_files(package_dir: Path, required: set[str]) -> list[str]:
    return sorted(name for name in required if not (package_dir / name).is_file())


def package_accepted(package: dict[str, Any]) -> bool:
    quality = package.get("quality")
    quality_accepted = isinstance(quality, dict) and quality.get("accepted") is True
    top_level_accepted = package.get("accepted", True) is True
    return quality_accepted and top_level_accepted


def load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return read_json(path)
    except (OSError, ValueError):
        return None


def is_matrix(value: object, rows: int, cols: int) -> bool:
    if not isinstance(value, list) or len(value) != rows:
        return False
    for row in value:
        if not isinstance(row, list) or len(row) != cols:
            return False
        if not all(isinstance(item, int | float) and not isinstance(item, bool) for item in row):
            return False
    return True


def failure(package_dir: Path, reason: str, missing: list[str]) -> dict[str, Any]:
    return {
        "schema_version": "calibration.package_verification.v1",
        "accepted": False,
        "package_dir": str(package_dir),
        "package_kind": "unknown",
        "missing_files": missing,
        "details": [reason],
    }


def result(
    package_dir: Path,
    package_kind: str,
    accepted: bool,
    missing: list[str],
    details: list[str],
    package: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "calibration.package_verification.v1",
        "accepted": accepted,
        "package_dir": str(package_dir),
        "package_kind": package_kind,
        "dry_run": package.get("dry_run") is True,
        "hardware_validated": package.get("hardware_validated") is True,
        "missing_files": missing,
        "details": details,
    }
