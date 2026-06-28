from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.artifacts import TARGET
from tennisbot_calibration.io import write_json

UVC_CONTROL_STRING = "brightness=64,gain=255,auto_exposure=1,exposure_time_absolute=2047"
NEAR_BLACK_MAX_LUMA = 8.0
LOW_CONTRAST_STD_LUMA = 3.0


def capture_mono_session(
    *,
    camera_id: str,
    device: str,
    output: Path,
    frame_count: int,
    interval_ms: int,
    width: int,
    height: int,
    fourcc: str,
    fps: int | None,
    dry_run: bool,
    prepare_uvc_controls: bool = False,
) -> dict[str, Any]:
    validate_capture_args(frame_count, interval_ms, width, height)
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []
    uvc_controls = prepare_uvc_device_controls([device], dry_run=dry_run) if prepare_uvc_controls else []

    if dry_run:
        for index in range(frame_count):
            rel_path = f"frames/{camera_id}_{index + 1:04d}.png"
            write_frame(frames_dir / f"{camera_id}_{index + 1:04d}.png", synthetic_frame(width, height, f"{camera_id} {index + 1}"))
            files.append(rel_path)
    else:
        capture = open_capture(device, width, height, fourcc, fps)
        try:
            for index in range(frame_count):
                ok, frame = capture.read()
                if not ok or frame is None:
                    raise RuntimeError(f"failed to read frame {index + 1} from {device}")
                rel_path = f"frames/{camera_id}_{index + 1:04d}.png"
                write_frame(frames_dir / f"{camera_id}_{index + 1:04d}.png", frame)
                files.append(rel_path)
                sleep_interval(interval_ms, index, frame_count)
        finally:
            capture.release()

    manifest = {
        "schema_version": "calibration.capture_session.v1",
        "topology": "mono",
        "session_id": output.name,
        "created_at": now_utc(),
        "dry_run": dry_run,
        "hardware_validated": not dry_run,
        "camera_id": camera_id,
        "device": device,
        "image_size": {"width": width, "height": height},
        "fourcc": fourcc,
        "fps": fps,
        "frame_count": len(files),
        "interval_ms": interval_ms,
        "uvc_controls": uvc_controls,
        "target": TARGET,
        "files": files,
        "next_step": "Run target detection and mono calibration solve for this session.",
    }
    write_json(output / "manifest.json", manifest)
    write_summary(output / "summary.md", manifest)
    write_review_html(output / "review.html", manifest)
    return manifest


def capture_stereo_session(
    *,
    left_camera_id: str,
    right_camera_id: str,
    left_device: str,
    right_device: str,
    output: Path,
    pair_count: int,
    interval_ms: int,
    width: int,
    height: int,
    fourcc: str,
    fps: int | None,
    dry_run: bool,
    prepare_uvc_controls: bool = False,
) -> dict[str, Any]:
    validate_capture_args(pair_count, interval_ms, width, height)
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[dict[str, Any]] = []
    uvc_controls = (
        prepare_uvc_device_controls([left_device, right_device], dry_run=dry_run) if prepare_uvc_controls else []
    )

    if dry_run:
        for index in range(pair_count):
            left_rel = f"frames/{left_camera_id}_{index + 1:04d}.png"
            right_rel = f"frames/{right_camera_id}_{index + 1:04d}.png"
            write_frame(frames_dir / f"{left_camera_id}_{index + 1:04d}.png", synthetic_frame(width, height, f"{left_camera_id} {index + 1}"))
            write_frame(frames_dir / f"{right_camera_id}_{index + 1:04d}.png", synthetic_frame(width, height, f"{right_camera_id} {index + 1}", shift=23))
            pairs.append({"index": index + 1, "left": left_rel, "right": right_rel})
    else:
        left_capture = open_capture(left_device, width, height, fourcc, fps)
        right_capture = open_capture(right_device, width, height, fourcc, fps)
        try:
            for index in range(pair_count):
                left_ok, left_frame = left_capture.read()
                right_ok, right_frame = right_capture.read()
                if not left_ok or left_frame is None:
                    raise RuntimeError(f"failed to read left frame {index + 1} from {left_device}")
                if not right_ok or right_frame is None:
                    raise RuntimeError(f"failed to read right frame {index + 1} from {right_device}")
                left_rel = f"frames/{left_camera_id}_{index + 1:04d}.png"
                right_rel = f"frames/{right_camera_id}_{index + 1:04d}.png"
                write_frame(frames_dir / f"{left_camera_id}_{index + 1:04d}.png", left_frame)
                write_frame(frames_dir / f"{right_camera_id}_{index + 1:04d}.png", right_frame)
                pairs.append({"index": index + 1, "left": left_rel, "right": right_rel})
                sleep_interval(interval_ms, index, pair_count)
        finally:
            left_capture.release()
            right_capture.release()

    manifest = {
        "schema_version": "calibration.capture_session.v1",
        "topology": "stereo",
        "session_id": output.name,
        "created_at": now_utc(),
        "dry_run": dry_run,
        "hardware_validated": not dry_run,
        "camera_ids": [left_camera_id, right_camera_id],
        "devices": {left_camera_id: left_device, right_camera_id: right_device},
        "image_size": {"width": width, "height": height},
        "fourcc": fourcc,
        "fps": fps,
        "pair_count": len(pairs),
        "interval_ms": interval_ms,
        "uvc_controls": uvc_controls,
        "target": TARGET,
        "pairs": pairs,
        "next_step": "Run target detection and stereo calibration solve for this session.",
    }
    write_json(output / "manifest.json", manifest)
    write_summary(output / "summary.md", manifest)
    write_review_html(output / "review.html", manifest)
    return manifest


def inspect_capture_session(*, session: Path, output_report: Path | None = None) -> dict[str, Any]:
    manifest_path = session / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"capture session manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = capture_session_image_entries(manifest)
    expected_size = manifest.get("image_size", {})
    expected_width = int(expected_size.get("width", 0))
    expected_height = int(expected_size.get("height", 0))

    frames: list[dict[str, Any]] = []
    session_issues: list[str] = []
    for entry in entries:
        frame_path = session / entry["path"]
        frame_result = inspect_frame(frame_path, expected_width=expected_width, expected_height=expected_height)
        frames.append({**entry, **frame_result})
        session_issues.extend(f"{entry['path']}: {issue}" for issue in frame_result["issues"])

    read_image_count = sum(1 for frame in frames if frame["status"] == "read")
    accepted = len(entries) > 0 and read_image_count == len(entries) and len(session_issues) == 0
    result = {
        "schema_version": "calibration.capture_inspection.v1",
        "session_id": manifest.get("session_id", session.name),
        "topology": manifest.get("topology"),
        "created_at": now_utc(),
        "session_path": str(session),
        "accepted": accepted,
        "ready_for_target_detection": accepted,
        "image_count": len(entries),
        "read_image_count": read_image_count,
        "expected_image_size": {"width": expected_width, "height": expected_height},
        "thresholds": {
            "near_black_max_luma": NEAR_BLACK_MAX_LUMA,
            "low_contrast_std_luma": LOW_CONTRAST_STD_LUMA,
        },
        "issues": session_issues,
        "frames": frames,
        "recommendation": inspection_recommendation(accepted),
    }
    write_json(session / "inspection.json", result)
    if output_report is not None:
        write_inspection_report(output_report, result)
    return result


def capture_session_image_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    topology = manifest.get("topology")
    if topology == "mono":
        return [
            {
                "index": index + 1,
                "camera_id": manifest.get("camera_id"),
                "side": "mono",
                "path": str(path),
            }
            for index, path in enumerate(manifest.get("files", []))
        ]
    if topology == "stereo":
        left_camera_id, right_camera_id = manifest.get("camera_ids", ["left", "right"])
        entries: list[dict[str, Any]] = []
        for pair in manifest.get("pairs", []):
            pair_index = int(pair.get("index", len(entries) // 2 + 1))
            entries.append(
                {
                    "index": pair_index,
                    "camera_id": left_camera_id,
                    "side": "left",
                    "path": str(pair["left"]),
                }
            )
            entries.append(
                {
                    "index": pair_index,
                    "camera_id": right_camera_id,
                    "side": "right",
                    "path": str(pair["right"]),
                }
            )
        return entries
    raise ValueError(f"unsupported capture session topology: {topology}")


def inspect_frame(path: Path, *, expected_width: int, expected_height: int) -> dict[str, Any]:
    issues: list[str] = []
    if not path.is_file():
        return {"status": "missing", "issues": ["missing image file"]}

    frame = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if frame is None:
        return {"status": "unreadable", "issues": ["unreadable image file"]}

    height, width = frame.shape[:2]
    if expected_width > 0 and expected_height > 0 and (width != expected_width or height != expected_height):
        issues.append(f"image size {width}x{height} does not match expected {expected_width}x{expected_height}")

    luma = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    mean_luma = float(luma.mean())
    std_luma = float(luma.std())
    min_luma = float(luma.min())
    max_luma = float(luma.max())
    non_black_pixel_percent = float((luma > NEAR_BLACK_MAX_LUMA).mean() * 100.0)
    if max_luma <= NEAR_BLACK_MAX_LUMA:
        issues.append("near-black frame")
    if std_luma <= LOW_CONTRAST_STD_LUMA:
        issues.append("low contrast / likely blank frame")

    return {
        "status": "read",
        "width": width,
        "height": height,
        "mean_luma": round(mean_luma, 3),
        "std_luma": round(std_luma, 3),
        "min_luma": round(min_luma, 3),
        "max_luma": round(max_luma, 3),
        "non_black_pixel_percent": round(non_black_pixel_percent, 3),
        "issues": issues,
    }


def write_inspection_report(path: Path, result: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    issue_lines = ["- none"] if not result["issues"] else [f"- {issue}" for issue in result["issues"]]
    frame_lines = [
        "| image | side | size | mean_luma | std_luma | max_luma | non_black_% | issues |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for frame in result["frames"]:
        size = f"{frame.get('width', '-')}x{frame.get('height', '-')}" if frame["status"] == "read" else "-"
        issues = ", ".join(frame["issues"]) if frame["issues"] else "none"
        frame_lines.append(
            "| "
            + " | ".join(
                [
                    f"`{frame['path']}`",
                    str(frame["side"]),
                    size,
                    str(frame.get("mean_luma", "-")),
                    str(frame.get("std_luma", "-")),
                    str(frame.get("max_luma", "-")),
                    str(frame.get("non_black_pixel_percent", "-")),
                    issues,
                ]
            )
            + " |"
        )

    lines = [
        "# Calibration Capture Session Inspection",
        "",
        f"- created_at: {result['created_at']}",
        f"- session_id: {result['session_id']}",
        f"- topology: {result['topology']}",
        f"- accepted: {result['accepted']}",
        f"- ready_for_target_detection: {result['ready_for_target_detection']}",
        f"- image_count: {result['image_count']}",
        f"- read_image_count: {result['read_image_count']}",
        f"- recommendation: {result['recommendation']}",
        "",
        "## Issues",
        "",
        *issue_lines,
        "",
        "## Frame Metrics",
        "",
        *frame_lines,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def inspection_recommendation(accepted: bool) -> str:
    if accepted:
        return "Proceed to target detection, then mono or stereo calibration solve."
    return "Recapture after fixing camera exposure, lighting, visibility, and calibration target placement."


def prepare_uvc_device_controls(devices: list[str], *, dry_run: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for device in ordered_unique(devices):
        if dry_run:
            results.append(
                {
                    "device": device,
                    "status": "skipped",
                    "controls": UVC_CONTROL_STRING,
                    "detail": "dry-run session; v4l2-ctl was not executed.",
                }
            )
            continue

        command = ["v4l2-ctl", "-d", device, f"--set-ctrl={UVC_CONTROL_STRING}"]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
        except FileNotFoundError as exc:
            raise RuntimeError("v4l2-ctl is required for --prepare-uvc-controls") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"timed out while applying UVC controls to {device}") from exc
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if completed.returncode != 0:
            detail = stderr or stdout or f"v4l2-ctl exited with {completed.returncode}"
            raise RuntimeError(f"failed to apply UVC controls to {device}: {detail}")
        results.append(
            {
                "device": device,
                "status": "passed",
                "controls": UVC_CONTROL_STRING,
                "returncode": completed.returncode,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
    return results


def ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def validate_capture_args(frame_count: int, interval_ms: int, width: int, height: int) -> None:
    if frame_count <= 0:
        raise ValueError("frame count must be positive")
    if interval_ms < 0:
        raise ValueError("interval_ms must be non-negative")
    if width <= 0 or height <= 0:
        raise ValueError("image size must be positive")


def open_capture(device: str, width: int, height: int, fourcc: str, fps: int | None) -> cv2.VideoCapture:
    capture = cv2.VideoCapture(parse_device(device), cv2.CAP_V4L2)
    if not capture.isOpened():
        raise RuntimeError(f"failed to open camera device {device}")
    if fourcc:
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc[:4]))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    if fps is not None:
        capture.set(cv2.CAP_PROP_FPS, fps)
    return capture


def parse_device(device: str) -> int | str:
    if device.isdigit():
        return int(device)
    return device


def synthetic_frame(width: int, height: int, label: str, *, shift: int = 0) -> np.ndarray:
    x_gradient = np.linspace(24 + shift, 180 + shift, width, dtype=np.float32) % 255
    y_gradient = np.linspace(12, 150, height, dtype=np.float32)
    blue = np.tile(x_gradient, (height, 1))
    green = np.tile(y_gradient.reshape(height, 1), (1, width))
    red = np.full((height, width), 96 + shift, dtype=np.float32) % 255
    frame = np.dstack([blue, green, red]).astype(np.uint8)
    cv2.putText(
        frame,
        label,
        (max(4, width // 20), max(18, height // 2)),
        cv2.FONT_HERSHEY_SIMPLEX,
        max(0.35, min(width, height) / 360.0),
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    return frame


def write_frame(path: Path, frame: np.ndarray) -> None:
    if not cv2.imwrite(str(path), frame):
        raise RuntimeError(f"failed to write frame {path}")


def sleep_interval(interval_ms: int, index: int, total: int) -> None:
    if interval_ms > 0 and index < total - 1:
        sleep(interval_ms / 1000.0)


def write_summary(path: Path, manifest: dict[str, Any]) -> None:
    lines = [
        "# Calibration Capture Session",
        "",
        f"- session_id: {manifest['session_id']}",
        f"- topology: {manifest['topology']}",
        f"- dry_run: {manifest['dry_run']}",
        f"- hardware_validated: {manifest['hardware_validated']}",
        f"- image_size: {manifest['image_size']['width']}x{manifest['image_size']['height']}",
        f"- fourcc: {manifest['fourcc']}",
        f"- fps: {manifest['fps']}",
        f"- interval_ms: {manifest['interval_ms']}",
    ]
    if manifest["topology"] == "mono":
        lines.extend(
            [
                f"- camera_id: {manifest['camera_id']}",
                f"- device: {manifest['device']}",
                f"- frame_count: {manifest['frame_count']}",
            ]
        )
    else:
        lines.extend(
            [
                f"- camera_ids: {', '.join(manifest['camera_ids'])}",
                f"- pair_count: {manifest['pair_count']}",
            ]
        )
    if manifest["uvc_controls"]:
        lines.extend(["", "## UVC Controls", ""])
        for item in manifest["uvc_controls"]:
            lines.append(f"- {item['device']}: {item['status']} ({item['controls']})")
    lines.extend(["", "## Next Step", "", manifest["next_step"], ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_html(path: Path, manifest: dict[str, Any]) -> None:
    if manifest["topology"] == "mono":
        items = "\n".join(f"<li><code>{name}</code></li>" for name in manifest["files"])
    else:
        items = "\n".join(
            f"<li>{pair['index']}: <code>{pair['left']}</code> / <code>{pair['right']}</code></li>"
            for pair in manifest["pairs"]
        )
    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Calibration Capture Session</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.45; color: #111827; }}
    code {{ background: #f3f4f6; padding: 0.1rem 0.25rem; }}
  </style>
</head>
<body>
  <h1>Calibration Capture Session</h1>
  <p><code>session_id</code>: {manifest['session_id']}</p>
  <p><code>topology</code>: {manifest['topology']}</p>
  <p><code>dry_run</code>: {manifest['dry_run']}</p>
  <p><code>hardware_validated</code>: {manifest['hardware_validated']}</p>
  <h2>Frames</h2>
  <ul>
    {items}
  </ul>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def now_utc() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
