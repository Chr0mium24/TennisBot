from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml


LEFT_CAMERA_ID = "left"
RIGHT_CAMERA_ID = "right"
IMAGE_NAME = "image.png"
DEFAULT_PREVIEW_MAX_SIZE = (1280, 720)


@dataclass(frozen=True)
class TargetConfig:
    profile: str = "dfoptix_charuco_14x9_square15mm_marker11_25mm"
    squares_x: int = 14
    squares_y: int = 9
    dictionary: str = "DICT_5X5_100"
    square_size_m: float = 0.015
    marker_size_m: float = 0.01125


@dataclass(frozen=True)
class CameraConfig:
    width_px: int = 1280
    height_px: int = 720
    fps: float = 30.0
    fourcc: str = "MJPG"
    camera_id: str = "cam1"


@dataclass(frozen=True)
class CaptureConfig:
    views: int = 30
    min_corners: int = 0
    min_corner_coverage: float = 1.0
    min_sharpness: float = 30.0
    min_capture_interval_s: float = 0.6
    max_views_per_bucket: int = 2
    position_bins_x: int = 8
    position_bins_y: int = 6
    stability_frames: int = 10
    stable_center_delta: float = 0.015
    stable_area_delta: float = 0.08
    dwell_capture_s: float = 2.0


@dataclass(frozen=True)
class ToolConfig:
    target: TargetConfig
    camera: CameraConfig
    capture: CaptureConfig


@dataclass(frozen=True)
class CharucoDetection:
    corners: np.ndarray | None
    ids: np.ndarray | None
    count: int
    mean_gray: float
    sharpness: float
    points: tuple[tuple[float, float], ...] = ()

    @property
    def accepted(self) -> bool:
        return self.count > 0


class OpenCVCamera:
    def __init__(self, device: str | int, config: CameraConfig) -> None:
        self.device = parse_device(device)
        self.capture = (
            cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            if isinstance(self.device, int)
            else cv2.VideoCapture(self.device)
        )
        if not self.capture.isOpened():
            raise RuntimeError(f"failed to open camera device: {device}")
        if config.fourcc:
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*config.fourcc[:4]))
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, float(config.width_px))
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, float(config.height_px))
        self.capture.set(cv2.CAP_PROP_FPS, float(config.fps))

    def read(self) -> np.ndarray:
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise RuntimeError(f"failed to read frame from camera device: {self.device}")
        return frame

    def release(self) -> None:
        self.capture.release()


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_device(value: str | int) -> str | int:
    if isinstance(value, int):
        return value
    if value.isdigit():
        return int(value)
    match = re.fullmatch(r"/dev/video(\d+)", value)
    return int(match.group(1)) if match else value


def load_config(path: Path) -> ToolConfig:
    payload: dict[str, Any] = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            payload = loaded
    target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
    camera = payload.get("camera") if isinstance(payload.get("camera"), dict) else {}
    capture = payload.get("capture") if isinstance(payload.get("capture"), dict) else {}
    return ToolConfig(
        target=TargetConfig(
            profile=str(target.get("profile", TargetConfig.profile)),
            squares_x=int(target.get("squares_x", TargetConfig.squares_x)),
            squares_y=int(target.get("squares_y", TargetConfig.squares_y)),
            dictionary=str(target.get("dictionary", TargetConfig.dictionary)),
            square_size_m=float(target.get("square_size_m", TargetConfig.square_size_m)),
            marker_size_m=float(target.get("marker_size_m", TargetConfig.marker_size_m)),
        ),
        camera=CameraConfig(
            width_px=int(camera.get("width_px", CameraConfig.width_px)),
            height_px=int(camera.get("height_px", CameraConfig.height_px)),
            fps=float(camera.get("fps", CameraConfig.fps)),
            fourcc=str(camera.get("fourcc", CameraConfig.fourcc)),
            camera_id=str(camera.get("camera_id", CameraConfig.camera_id)),
        ),
        capture=CaptureConfig(
            views=int(capture.get("views", CaptureConfig.views)),
            min_corners=int(capture.get("min_corners", CaptureConfig.min_corners)),
            min_corner_coverage=float(capture.get("min_corner_coverage", CaptureConfig.min_corner_coverage)),
            min_sharpness=float(capture.get("min_sharpness", CaptureConfig.min_sharpness)),
            min_capture_interval_s=float(capture.get("min_capture_interval_s", CaptureConfig.min_capture_interval_s)),
            max_views_per_bucket=int(capture.get("max_views_per_bucket", CaptureConfig.max_views_per_bucket)),
            position_bins_x=int(capture.get("position_bins_x", CaptureConfig.position_bins_x)),
            position_bins_y=int(capture.get("position_bins_y", CaptureConfig.position_bins_y)),
            stability_frames=int(capture.get("stability_frames", CaptureConfig.stability_frames)),
            stable_center_delta=float(capture.get("stable_center_delta", CaptureConfig.stable_center_delta)),
            stable_area_delta=float(capture.get("stable_area_delta", CaptureConfig.stable_area_delta)),
            dwell_capture_s=float(capture.get("dwell_capture_s", CaptureConfig.dwell_capture_s)),
        ),
    )


def fresh_output_dir(path: Path) -> Path:
    if not path.exists():
        return path
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    candidate = path.with_name(f"{path.name}_{stamp}")
    if not candidate.exists():
        return candidate
    for index in range(2, 1000):
        candidate = path.with_name(f"{path.name}_{stamp}_{index:02d}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"could not allocate fresh output directory for {path}")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def preview_size(frame: np.ndarray, max_width: int = 960) -> tuple[int, int]:
    height, width = frame.shape[:2]
    if width <= max_width:
        return width, height
    scale = max_width / float(width)
    return max_width, max(1, int(height * scale))


def preview_display_size(frame_shape: tuple[int, ...], max_size: tuple[int, int] = DEFAULT_PREVIEW_MAX_SIZE) -> tuple[int, int]:
    height, width = int(frame_shape[0]), int(frame_shape[1])
    max_width, max_height = max_size
    if width <= max_width and height <= max_height:
        return width, height
    scale = min(max_width / width, max_height / height)
    return max(1, int(round(width * scale))), max(1, int(round(height * scale)))


def resized_preview_frame(frame: np.ndarray, display_size: tuple[int, int]) -> np.ndarray:
    height, width = frame.shape[:2]
    if display_size == (width, height):
        return frame.copy()
    return cv2.resize(frame, display_size, interpolation=cv2.INTER_AREA)


def target_json(target: TargetConfig) -> dict[str, Any]:
    return {
        "type": "charuco",
        "profile": target.profile,
        "squares_x": target.squares_x,
        "squares_y": target.squares_y,
        "dictionary": target.dictionary,
        "square_size_m": target.square_size_m,
        "marker_size_m": target.marker_size_m,
    }


def camera_json(camera_id: str, camera: CameraConfig, device: str | int | None = None) -> dict[str, Any]:
    return {
        "camera_id": camera_id,
        "width_px": camera.width_px,
        "height_px": camera.height_px,
        "fps": camera.fps,
        "device": None if device is None else str(device),
    }


def stereo_rig_json(config: CameraConfig, left_device: str | int, right_device: str | int) -> dict[str, Any]:
    return {
        "rig_id": "stereo",
        "left": camera_json(LEFT_CAMERA_ID, config, left_device),
        "right": camera_json(RIGHT_CAMERA_ID, config, right_device),
        "metadata": {},
    }
