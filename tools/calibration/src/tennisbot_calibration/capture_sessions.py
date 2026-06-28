from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

import cv2
import numpy as np

from tennisbot_calibration.artifacts import TARGET
from tennisbot_calibration.io import write_json


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
) -> dict[str, Any]:
    validate_capture_args(frame_count, interval_ms, width, height)
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    files: list[str] = []

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
) -> dict[str, Any]:
    validate_capture_args(pair_count, interval_ms, width, height)
    output.mkdir(parents=True, exist_ok=True)
    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    pairs: list[dict[str, Any]] = []

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
        "target": TARGET,
        "pairs": pairs,
        "next_step": "Run target detection and stereo calibration solve for this session.",
    }
    write_json(output / "manifest.json", manifest)
    write_summary(output / "summary.md", manifest)
    write_review_html(output / "review.html", manifest)
    return manifest


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
