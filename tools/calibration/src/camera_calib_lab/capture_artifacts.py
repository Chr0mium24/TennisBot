from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np

from camera_calib_lab.capture_quality import AutoCaptureQuality
from camera_calib_lab.capture_types import (
    IMAGE_NAME,
    LEFT_CAMERA_ID,
    RIGHT_CAMERA_ID,
    CharucoDetection,
    ToolConfig,
    camera_json,
    stereo_rig_json,
    target_json,
    utc_now_iso,
    write_json,
)
from camera_calib_lab.charuco_detection import detected_ids


def save_mono_frame(
    output: Path,
    frame: np.ndarray,
    detection: CharucoDetection,
    quality: AutoCaptureQuality,
    camera_id: str,
    index: int,
    manual: bool = False,
) -> dict[str, Any]:
    view_id = f"view{index + 1:03d}"
    view_dir = output / camera_id / view_id
    view_dir.mkdir(parents=True, exist_ok=True)
    image_path = view_dir / IMAGE_NAME
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"failed to write {image_path}")
    metadata = quality_metadata(quality)
    metadata["auto_capture"] = not manual
    metadata["manual_capture"] = bool(manual)
    record = {
        "view_id": view_id,
        "camera_id": camera_id,
        "paths": [str(image_path)],
        "frame_role": "passive",
        "quality": metadata,
        "detected_point_count": detection.count,
        "detected_ids": detected_ids(detection),
    }
    write_json(view_dir / "metadata.json", record)
    return record


def save_stereo_pair(
    output: Path,
    left_frame: np.ndarray,
    right_frame: np.ndarray,
    left_detection: CharucoDetection,
    right_detection: CharucoDetection,
    left_quality: AutoCaptureQuality,
    right_quality: AutoCaptureQuality,
    index: int,
    manual: bool = False,
) -> dict[str, Any]:
    view_id = f"view{index + 1:03d}"
    left_record = save_stereo_camera_frame(output, LEFT_CAMERA_ID, view_id, left_frame, left_detection, left_quality, manual)
    right_record = save_stereo_camera_frame(output, RIGHT_CAMERA_ID, view_id, right_frame, right_detection, right_quality, manual)
    record = {
        "view_id": view_id,
        "frame_role": "passive",
        "left": left_record,
        "right": right_record,
        "quality": {
            "accepted": bool(left_quality.accepted and right_quality.accepted),
            "left_corner_count": int(left_quality.corner_count),
            "right_corner_count": int(right_quality.corner_count),
            "required_corners": int(max(left_quality.required_corners, right_quality.required_corners)),
            "position_bucket": left_quality.position_bucket,
            "stable_frame_count": int(min(left_quality.stable_frame_count, right_quality.stable_frame_count)),
            "manual_capture": bool(manual),
            "auto_capture": not manual,
        },
    }
    write_json(output / "pairs" / f"{view_id}.json", record)
    return record


def save_stereo_camera_frame(
    output: Path,
    camera_id: str,
    view_id: str,
    frame: np.ndarray,
    detection: CharucoDetection,
    quality: AutoCaptureQuality,
    manual: bool,
) -> dict[str, Any]:
    view_dir = output / camera_id / view_id
    view_dir.mkdir(parents=True, exist_ok=True)
    image_path = view_dir / IMAGE_NAME
    if not cv2.imwrite(str(image_path), frame):
        raise RuntimeError(f"failed to write {image_path}")
    metadata = quality_metadata(quality)
    metadata["auto_capture"] = not manual
    metadata["manual_capture"] = bool(manual)
    record = {
        "view_id": view_id,
        "camera_id": camera_id,
        "paths": [str(image_path)],
        "frame_role": "passive",
        "quality": metadata,
        "detected_point_count": detection.count,
        "detected_ids": detected_ids(detection),
    }
    write_json(view_dir / "metadata.json", record)
    return record


def quality_metadata(quality: AutoCaptureQuality) -> dict[str, Any]:
    return {
        "mean_gray": float(quality.mean_gray),
        "exposure_usable": bool(quality.exposure_ok),
        "sharpness": float(quality.sharpness),
        "corner_count": int(quality.corner_count),
        "required_corners": int(quality.required_corners),
        "center_x": quality.center_x,
        "center_y": quality.center_y,
        "area_ratio": quality.area_ratio,
        "position_bucket": quality.position_bucket,
        "stable": bool(quality.stable),
        "stable_frame_count": int(quality.stable_frame_count),
    }


def mono_manifest(
    *,
    output: Path,
    config: ToolConfig,
    device: str | int,
    v4l2_controls: dict[str, Any] | None,
    records: list[dict[str, Any]],
    bucket_counts: dict[str, int],
    total_frame_count: int,
    qualified_frame_count: int,
    calibrate_requested: bool,
    calibration_output: Path | None,
) -> dict[str, Any]:
    ready = len(records) >= config.capture.views
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "status": "ready" if ready else "partial",
        "session_root": str(output),
        "target": target_json(config.target),
        "camera": camera_json(config.camera.camera_id, config.camera, device, v4l2_controls),
        "topology": "mono",
        "frame_count": len(records),
        "total_frame_count": int(total_frame_count),
        "qualified_frame_count": int(qualified_frame_count),
        "dry_run": False,
        "hardware_validated": True,
        "interactive": True,
        "auto_capture": True,
        "calibrate_ready": ready,
        "calibrate_requested": bool(calibrate_requested),
        "calibration_output": None if calibration_output is None else str(calibration_output),
        "method": "charuco.mono.opencv",
        "session": "session.json",
        "frames": records,
        "coverage": {
            "position_buckets": bucket_counts,
            "unique_position_buckets": len(bucket_counts),
            "target_views": config.capture.views,
            "dwell_capture_s": float(config.capture.dwell_capture_s),
            "stability_frames": int(config.capture.stability_frames),
        },
    }


def stereo_manifest(
    *,
    output: Path,
    config: ToolConfig,
    left_device: str | int,
    right_device: str | int,
    left_v4l2_controls: dict[str, Any] | None,
    right_v4l2_controls: dict[str, Any] | None,
    pair_records: list[dict[str, Any]],
    bucket_counts: dict[str, int],
    total_pair_frame_count: int,
    qualified_pair_count: int,
    calibrate_requested: bool,
    calibration_output: Path | None,
) -> dict[str, Any]:
    ready = len(pair_records) >= config.capture.views
    return {
        "schema_version": 1,
        "created_at": utc_now_iso(),
        "status": "ready" if ready else "partial",
        "session_root": str(output),
        "target": target_json(config.target),
        "stereo_rig": stereo_rig_json(
            config.camera,
            left_device,
            right_device,
            left_v4l2_controls,
            right_v4l2_controls,
        ),
        "topology": "stereo",
        "pair_count": len(pair_records),
        "frame_count": 2 * len(pair_records),
        "total_pair_frame_count": int(total_pair_frame_count),
        "qualified_pair_count": int(qualified_pair_count),
        "dry_run": False,
        "hardware_validated": True,
        "interactive": True,
        "auto_capture": True,
        "calibrate_ready": ready,
        "calibrate_requested": bool(calibrate_requested),
        "calibration_output": None if calibration_output is None else str(calibration_output),
        "method": "charuco.stereo.opencv",
        "session": "session.json",
        "pairs": pair_records,
        "coverage": {
            "position_buckets": bucket_counts,
            "unique_position_buckets": len(bucket_counts),
            "target_pairs": config.capture.views,
            "dwell_capture_s": float(config.capture.dwell_capture_s),
            "stability_frames": int(config.capture.stability_frames),
        },
    }


def mono_session_json(
    output: Path,
    config: ToolConfig,
    device: str | int,
    records: list[dict[str, Any]],
    v4l2_controls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "session_id": output.name,
        "topology": "mono",
        "target": target_json(config.target),
        "camera": camera_json(config.camera.camera_id, config.camera, device, v4l2_controls),
        "frames": [
            {
                "view_id": item["view_id"],
                "camera_id": item["camera_id"],
                "frame_paths": item["paths"],
                "frame_role": "passive",
                "metadata": item["quality"],
            }
            for item in records
        ],
        "created_at": utc_now_iso(),
        "source": "real",
        "metadata": {"capture_backend": "opencv_charuco_auto", "device": str(device), "method_id": "charuco.mono.opencv"},
    }


def stereo_session_json(
    output: Path,
    config: ToolConfig,
    left_device: str | int,
    right_device: str | int,
    pair_records: list[dict[str, Any]],
    left_v4l2_controls: dict[str, Any] | None = None,
    right_v4l2_controls: dict[str, Any] | None = None,
) -> dict[str, Any]:
    frames = []
    for pair in pair_records:
        for side in (LEFT_CAMERA_ID, RIGHT_CAMERA_ID):
            item = pair[side]
            frames.append(
                {
                    "view_id": item["view_id"],
                    "camera_id": item["camera_id"],
                    "frame_paths": item["paths"],
                    "frame_role": "passive",
                    "metadata": item["quality"],
                }
            )
    return {
        "session_id": output.name,
        "topology": "stereo",
        "target": target_json(config.target),
        "stereo_rig": stereo_rig_json(
            config.camera,
            left_device,
            right_device,
            left_v4l2_controls,
            right_v4l2_controls,
        ),
        "frames": frames,
        "created_at": utc_now_iso(),
        "source": "real",
        "metadata": {
            "capture_backend": "opencv_stereo_charuco_auto",
            "left_device": str(left_device),
            "right_device": str(right_device),
            "method_id": "charuco.stereo.opencv",
        },
    }


def write_mono_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# ChArUco Capture Session",
        "",
        f"- status: {manifest['status']}",
        f"- target: {manifest['target']['profile']}",
        f"- camera: {manifest['camera']['camera_id']} {manifest['camera']['width_px']} x {manifest['camera']['height_px']} px",
        f"- frames: {manifest['frame_count']}",
        f"- calibrate requested: {manifest['calibrate_requested']}",
        "",
        "| view | frame | corners |",
        "|---|---|---:|",
    ]
    for frame in manifest["frames"]:
        lines.append(f"| {frame['view_id']} | {frame['paths'][0]} | {frame['detected_point_count']} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_stereo_summary(path: Path, manifest: dict[str, Any]) -> None:
    rig = manifest["stereo_rig"]
    lines = [
        "# Stereo ChArUco Capture Session",
        "",
        f"- status: {manifest['status']}",
        f"- target: {manifest['target']['profile']}",
        f"- left camera: {rig['left']['camera_id']} {rig['left']['width_px']} x {rig['left']['height_px']} px",
        f"- right camera: {rig['right']['camera_id']} {rig['right']['width_px']} x {rig['right']['height_px']} px",
        f"- stereo pairs: {manifest['pair_count']}",
        f"- saved frame sets: {manifest['frame_count']}",
        f"- calibrate requested: {manifest['calibrate_requested']}",
        "",
        "| view | left frame | right frame | left corners | right corners |",
        "|---|---|---|---:|---:|",
    ]
    for pair in manifest["pairs"]:
        lines.append(
            "| "
            f"{pair['view_id']} | "
            f"{pair['left']['paths'][0]} | "
            f"{pair['right']['paths'][0]} | "
            f"{pair['left']['detected_point_count']} | "
            f"{pair['right']['detected_point_count']} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
