from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def capture_summary(manifest: dict[str, Any]) -> str:
    status = str(manifest.get("status", "unknown"))
    result = str(manifest.get("session_root", ""))
    topology = manifest.get("topology")
    if topology == "stereo":
        return (
            f"capture status={status} pairs={manifest.get('pair_count', 0)} "
            f"points={stereo_capture_points(manifest)} images={stereo_image_pattern(manifest)} result={result}"
        )
    return (
        f"capture status={status} views={manifest.get('frame_count', 0)} "
        f"points={mono_capture_points(manifest)} images={mono_image_pattern(manifest)} result={result}"
    )


def mono_solve_summary(package: dict[str, Any], verification: dict[str, Any], output_path: Path) -> str:
    quality = package["quality"]
    source = str(package.get("source_session", ""))
    return (
        f"solve status={accepted_label(package)} views={quality['accepted_view_count']}/{quality['total_view_count']} "
        f"points={verification_point_summary(verification)} rms={format_px(quality['rms_reprojection_px'])} "
        f"images={source_image_pattern(source, topology='mono', camera_id=str(package['camera_id']))} "
        f"result={output_path.as_posix()}"
    )


def stereo_solve_summary(package: dict[str, Any], output_path: Path) -> str:
    quality = package["quality"]
    source = str(package.get("source_session", ""))
    epipolar = quality.get("epipolar_rms_px")
    epipolar_text = "" if epipolar is None else f" epipolar={format_px(epipolar)}"
    warning_text = " warning=runtime_quality" if package.get("runtime_quality_warning") else ""
    return (
        f"solve status={accepted_label(package)} pairs={quality['accepted_pair_count']}/{quality['total_pair_count']} "
        f"points={source_point_summary(source, topology='stereo')} "
        f"rms={format_px(quality['stereo_rms_reprojection_px'])}{epipolar_text}{warning_text} "
        f"images={source_image_pattern(source, topology='stereo')} result={output_path.as_posix()}"
    )


def accepted_label(package: dict[str, Any]) -> str:
    return "accepted" if package.get("accepted") is True else "rejected"


def mono_capture_points(manifest: dict[str, Any]) -> str:
    return point_summary(
        [point_count_from_record(frame) for frame in manifest.get("frames", []) if isinstance(frame, dict)]
    )


def stereo_capture_points(manifest: dict[str, Any]) -> str:
    left_points = []
    right_points = []
    for pair in manifest.get("pairs", []):
        if not isinstance(pair, dict):
            continue
        left_points.append(point_count_from_record(pair.get("left", {})))
        right_points.append(point_count_from_record(pair.get("right", {})))
    return f"left:{point_summary(left_points)} right:{point_summary(right_points)}"


def verification_point_summary(verification: dict[str, Any]) -> str:
    coverage = verification.get("coverage", {})
    if not isinstance(coverage, dict):
        return "unknown"
    return point_summary([coverage.get("corner_count_min"), coverage.get("corner_count_max")])


def source_point_summary(source: str, *, topology: str) -> str:
    payload = read_source_payload(source)
    if payload is None:
        return "unknown"
    if "frames" in payload:
        return session_point_summary(payload, topology=topology)
    if "views" in payload:
        return observations_point_summary(payload, topology=topology)
    return "unknown"


def session_point_summary(payload: dict[str, Any], *, topology: str) -> str:
    if topology == "stereo":
        left_points: list[int | None] = []
        right_points: list[int | None] = []
        for frame in payload.get("frames", []):
            if not isinstance(frame, dict):
                continue
            if frame.get("camera_id") == "left":
                left_points.append(point_count_from_record(frame))
            elif frame.get("camera_id") == "right":
                right_points.append(point_count_from_record(frame))
        return f"left:{point_summary(left_points)} right:{point_summary(right_points)}"
    return point_summary(
        [point_count_from_record(frame) for frame in payload.get("frames", []) if isinstance(frame, dict)]
    )


def observations_point_summary(payload: dict[str, Any], *, topology: str) -> str:
    if topology == "stereo":
        left_points: list[int | None] = []
        right_points: list[int | None] = []
        for view in payload.get("views", []):
            if not isinstance(view, dict):
                continue
            if view.get("side") == "left":
                left_points.append(image_point_count(view))
            elif view.get("side") == "right":
                right_points.append(image_point_count(view))
        return f"left:{point_summary(left_points)} right:{point_summary(right_points)}"
    return point_summary([image_point_count(view) for view in payload.get("views", []) if isinstance(view, dict)])


def image_point_count(view: dict[str, Any]) -> int | None:
    image_points = view.get("image_points")
    return len(image_points) if isinstance(image_points, list) else None


def point_count_from_record(record: Any) -> int | None:
    if not isinstance(record, dict):
        return None
    for key in ("detected_point_count", "corner_count"):
        value = record.get(key)
        if isinstance(value, int | float):
            return int(value)
    metadata = record.get("metadata") or record.get("quality")
    if isinstance(metadata, dict):
        value = metadata.get("corner_count")
        if isinstance(value, int | float):
            return int(value)
    return None


def point_summary(values: list[Any]) -> str:
    cleaned = [int(value) for value in values if isinstance(value, int | float)]
    if not cleaned:
        return "unknown"
    minimum = min(cleaned)
    maximum = max(cleaned)
    return str(minimum) if minimum == maximum else f"{minimum}-{maximum}"


def mono_image_pattern(manifest: dict[str, Any]) -> str:
    root = str(manifest.get("session_root", ""))
    camera = manifest.get("camera", {})
    camera_id = camera.get("camera_id", "cam") if isinstance(camera, dict) else "cam"
    return image_pattern(root, str(camera_id))


def stereo_image_pattern(manifest: dict[str, Any]) -> str:
    root = str(manifest.get("session_root", ""))
    rig = manifest.get("stereo_rig", {})
    left = rig.get("left", {}) if isinstance(rig, dict) else {}
    right = rig.get("right", {}) if isinstance(rig, dict) else {}
    left_id = left.get("camera_id", "left") if isinstance(left, dict) else "left"
    right_id = right.get("camera_id", "right") if isinstance(right, dict) else "right"
    return f"left:{image_pattern(root, str(left_id))} right:{image_pattern(root, str(right_id))}"


def source_image_pattern(source: str, *, topology: str, camera_id: str = "cam1") -> str:
    source_path = Path(source)
    root = source_path if source_path.is_dir() else source_path.parent
    if topology == "stereo":
        return f"left:{image_pattern(root.as_posix(), 'left')} right:{image_pattern(root.as_posix(), 'right')}"
    return image_pattern(root.as_posix(), camera_id)


def image_pattern(root: str, camera_id: str) -> str:
    return (Path(root) / camera_id / "view*" / "image.png").as_posix()


def read_source_payload(source: str) -> dict[str, Any] | None:
    if source == "":
        return None
    path = Path(source)
    if path.is_dir():
        path = path / "session.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def format_px(value: Any) -> str:
    return f"{float(value):.4f}px"
