from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.capture_sessions import capture_session_image_entries, now_utc
from tennisbot_calibration.io import write_json

DEFAULT_CHARUCO_PROFILE = {
    "profile": "dfoptix_charuco_15mm",
    "squares_x": 14,
    "squares_y": 9,
    "square_size_m": 0.015,
    "marker_size_m": 0.011,
    "dictionary": "DICT_5X5_100",
}


def detect_charuco_session(
    *,
    session: Path,
    output: Path | None = None,
    output_report: Path | None = None,
    min_corners: int = 6,
) -> dict[str, Any]:
    if min_corners <= 0:
        raise ValueError("min_corners must be positive")

    manifest_path = session / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"capture session manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    target = charuco_target_from_manifest(manifest)
    board = charuco_board(target)
    detector = cv2.aruco.CharucoDetector(board)

    entries = capture_session_image_entries(manifest)
    views = [detect_charuco_frame(session, entry, board, detector, min_corners) for entry in entries]
    accepted_view_count = sum(1 for view in views if view["accepted"])
    pairs = stereo_pair_observations(manifest, views)
    accepted_pair_count = sum(1 for pair in pairs if pair["accepted"])
    topology = manifest.get("topology")
    accepted = accepted_pair_count > 0 if topology == "stereo" else accepted_view_count > 0
    output_path = output or session / "observations.json"
    result = {
        "schema_version": "calibration.charuco_observations.v1",
        "session_id": manifest.get("session_id", session.name),
        "topology": topology,
        "created_at": now_utc(),
        "session_path": str(session),
        "output_path": str(output_path),
        "target": target,
        "detector": {"id": "charuco.opencv", "min_corners": min_corners},
        "accepted": accepted,
        "accepted_view_count": accepted_view_count,
        "total_view_count": len(views),
        "accepted_pair_count": accepted_pair_count if topology == "stereo" else None,
        "total_pair_count": len(pairs) if topology == "stereo" else None,
        "views": views,
        "pairs": pairs,
        "recommendation": detection_recommendation(accepted, topology),
    }
    write_json(output_path, result)
    if output_report is not None:
        write_detection_report(output_report, result)
    return result


def charuco_target_from_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    target = {**DEFAULT_CHARUCO_PROFILE, **manifest.get("target", {})}
    if target.get("type") != "charuco":
        raise ValueError("detect-charuco requires a charuco capture target")
    return target


def charuco_board(target: dict[str, Any]) -> cv2.aruco.CharucoBoard:
    dictionary_name = str(target.get("dictionary", DEFAULT_CHARUCO_PROFILE["dictionary"]))
    dictionary_id = getattr(cv2.aruco, dictionary_name, None)
    if dictionary_id is None:
        raise ValueError(f"unknown OpenCV ArUco dictionary: {dictionary_name}")
    dictionary = cv2.aruco.getPredefinedDictionary(dictionary_id)
    return cv2.aruco.CharucoBoard(
        (int(target["squares_x"]), int(target["squares_y"])),
        float(target["square_size_m"]),
        float(target["marker_size_m"]),
        dictionary,
    )


def detect_charuco_frame(
    session: Path,
    entry: dict[str, Any],
    board: cv2.aruco.CharucoBoard,
    detector: cv2.aruco.CharucoDetector,
    min_corners: int,
) -> dict[str, Any]:
    frame_path = session / entry["path"]
    base = {
        "index": entry["index"],
        "camera_id": entry["camera_id"],
        "side": entry["side"],
        "path": entry["path"],
    }
    if not frame_path.is_file():
        return {**base, "accepted": False, "corner_count": 0, "marker_count": 0, "rejection_reason": "missing image file"}

    image = cv2.imread(str(frame_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return {
            **base,
            "accepted": False,
            "corner_count": 0,
            "marker_count": 0,
            "rejection_reason": "unreadable image file",
        }

    corners, ids, _marker_corners, marker_ids = detector.detectBoard(image)
    corner_count = 0 if ids is None else int(len(ids))
    marker_count = 0 if marker_ids is None else int(len(marker_ids))
    if corners is None or ids is None or corner_count < min_corners:
        return {
            **base,
            "accepted": False,
            "image_size": {"width": int(image.shape[1]), "height": int(image.shape[0])},
            "corner_count": corner_count,
            "marker_count": marker_count,
            "rejection_reason": f"detected {corner_count} ChArUco corners, need at least {min_corners}",
        }

    object_points, image_points = board.matchImagePoints(corners, ids)
    object_array = np.asarray(object_points, dtype=np.float64).reshape(-1, 3)
    image_array = np.asarray(image_points, dtype=np.float64).reshape(-1, 2)
    return {
        **base,
        "accepted": True,
        "image_size": {"width": int(image.shape[1]), "height": int(image.shape[0])},
        "corner_count": corner_count,
        "marker_count": marker_count,
        "ids": [int(item) for item in ids.reshape(-1).tolist()],
        "image_points": [[float(col) for col in row] for row in image_array.tolist()],
        "object_points": [[float(col) for col in row] for row in object_array.tolist()],
    }


def stereo_pair_observations(manifest: dict[str, Any], views: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if manifest.get("topology") != "stereo":
        return []
    by_key = {(view["index"], view["side"]): view for view in views}
    pairs = []
    for pair in manifest.get("pairs", []):
        index = int(pair.get("index", len(pairs) + 1))
        left = by_key.get((index, "left"))
        right = by_key.get((index, "right"))
        left_accepted = bool(left and left["accepted"])
        right_accepted = bool(right and right["accepted"])
        pairs.append(
            {
                "index": index,
                "accepted": left_accepted and right_accepted,
                "left_corner_count": int(left.get("corner_count", 0)) if left else 0,
                "right_corner_count": int(right.get("corner_count", 0)) if right else 0,
                "left_rejection_reason": None if left_accepted else (left or {}).get("rejection_reason", "missing left view"),
                "right_rejection_reason": None if right_accepted else (right or {}).get("rejection_reason", "missing right view"),
            }
        )
    return pairs


def write_detection_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    view_lines = [
        "| image | side | accepted | corners | markers | reason |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for view in result["views"]:
        view_lines.append(
            "| "
            + " | ".join(
                [
                    f"`{view['path']}`",
                    str(view["side"]),
                    str(view["accepted"]),
                    str(view["corner_count"]),
                    str(view["marker_count"]),
                    str(view.get("rejection_reason", "none")),
                ]
            )
            + " |"
        )

    lines = [
        "# Calibration ChArUco Detection",
        "",
        f"- created_at: {result['created_at']}",
        f"- session_id: {result['session_id']}",
        f"- topology: {result['topology']}",
        f"- accepted: {result['accepted']}",
        f"- accepted_view_count: {result['accepted_view_count']} / {result['total_view_count']}",
    ]
    if result["topology"] == "stereo":
        lines.append(f"- accepted_pair_count: {result['accepted_pair_count']} / {result['total_pair_count']}")
    lines.extend(
        [
            f"- recommendation: {result['recommendation']}",
            "",
            "## Views",
            "",
            *view_lines,
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def detection_recommendation(accepted: bool, topology: object) -> str:
    if accepted and topology == "stereo":
        return "Proceed to stereo calibration solve after mono intrinsics are available."
    if accepted:
        return "Proceed to mono calibration solve for this camera."
    return "Recapture with the ChArUco target visible, sharp, and well lit before solving."
