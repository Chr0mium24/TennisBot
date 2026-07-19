from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import yaml
from tennisbot_camera.config import load_camera_config


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TOOL_ROOT.parents[1]
DEFAULT_CONFIG_PATH = TOOL_ROOT / "configs" / "tennis_camera_recording.yaml"

ControlValue = int | float | str | None


@dataclass(frozen=True)
class CaptureConfig:
    width: int
    height: int
    fps: float
    input_format: str
    pixel_format: str
    settle_seconds: float

    @property
    def video_size(self) -> str:
        return f"{self.width}x{self.height}"


@dataclass(frozen=True)
class RecordingDefaults:
    output_root: Path
    container: str
    sample_fps: float | None
    thread_queue_size: int


@dataclass(frozen=True)
class SingleCameraDefaults:
    device: str
    output_label: str


@dataclass(frozen=True)
class DualCameraDefaults:
    devices: tuple[str, ...]
    preview: bool
    soft_sync: bool
    parallel_capture: bool


@dataclass(frozen=True)
class PreviewDefaults:
    width: int
    fps: float
    port: int


@dataclass(frozen=True)
class RecordingConfig:
    path: Path
    schema_version: str
    capture: CaptureConfig
    recording: RecordingDefaults
    single: SingleCameraDefaults
    dual: DualCameraDefaults
    preview: PreviewDefaults
    controls: dict[str, ControlValue]

    def with_control_overrides(self, overrides: dict[str, ControlValue]) -> RecordingConfig:
        controls = dict(self.controls)
        controls.update({key: value for key, value in overrides.items() if value is not None})
        return replace(self, controls=controls)

    def v4l2_controls(self) -> list[tuple[str, ControlValue]]:
        return [(name, value) for name, value in self.controls.items() if value is not None]

    def v4l2_controls_string(self) -> str:
        return ",".join(f"{name}={format_control_value(value)}" for name, value in self.v4l2_controls())


def load_config(path: Path | str | None = None) -> RecordingConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_absolute():
        config_path = (Path.cwd() / config_path).resolve()
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"config must be a YAML mapping: {config_path}")
    config = parse_config(data, config_path)
    if config_path.resolve() == DEFAULT_CONFIG_PATH.resolve():
        camera_config = load_camera_config()
        config = replace(
            config,
            capture=replace(
                config.capture,
                width=camera_config.capture.width,
                height=camera_config.capture.height,
                fps=camera_config.capture.fps,
                pixel_format=camera_config.capture.pixel_format,
            ),
            single=replace(config.single, device=camera_config.camera("cam1").device),
            dual=replace(
                config.dual,
                devices=(camera_config.camera("cam1").device, camera_config.camera("cam2").device),
            ),
            controls=dict(camera_config.profile("recording")),
        )
    return config


def parse_config(data: dict[str, Any], path: Path) -> RecordingConfig:
    schema_version = str(data.get("schema_version", ""))
    if schema_version != "tennisbot.recording.config.v1":
        raise ValueError(f"unsupported recording config schema_version: {schema_version}")

    capture_data = require_mapping(data, "capture")
    recording_data = require_mapping(data, "recording")
    single_data = require_mapping(data, "single")
    dual_data = require_mapping(data, "dual")
    preview_data = require_mapping(data, "preview")
    controls_data = require_mapping(data, "controls")

    capture = CaptureConfig(
        width=positive_int(capture_data, "width"),
        height=positive_int(capture_data, "height"),
        fps=positive_float(capture_data, "fps"),
        input_format=str(capture_data.get("input_format", "mjpeg")),
        pixel_format=str(capture_data.get("pixel_format", "MJPG")),
        settle_seconds=non_negative_float(capture_data, "settle_seconds", default=1.0),
    )
    recording = RecordingDefaults(
        output_root=repo_path(str(recording_data.get("output_root", "runs/recording"))),
        container=container_value(str(recording_data.get("container", "mkv"))),
        sample_fps=optional_positive_float(recording_data.get("sample_fps")),
        thread_queue_size=positive_int(recording_data, "thread_queue_size", default=1024),
    )
    single = SingleCameraDefaults(
        device=str(single_data.get("device", "/dev/video0")),
        output_label=safe_label(str(single_data.get("output_label", "video0"))),
    )
    dual_devices = tuple(str(device) for device in dual_data.get("devices", ("/dev/video2", "/dev/video0")))
    if len(dual_devices) != 2 or not all(dual_devices):
        raise ValueError("dual.devices must contain exactly two devices")
    dual = DualCameraDefaults(
        devices=dual_devices,
        preview=bool(dual_data.get("preview", False)),
        soft_sync=bool(dual_data.get("soft_sync", True)),
        parallel_capture=bool(dual_data.get("parallel_capture", True)),
    )
    preview = PreviewDefaults(
        width=positive_int(preview_data, "width", default=960),
        fps=positive_float(preview_data, "fps", default=10.0),
        port=positive_int(preview_data, "port", default=23456),
    )
    controls = {str(name): normalize_control_value(value) for name, value in controls_data.items()}
    return RecordingConfig(
        path=path,
        schema_version=schema_version,
        capture=capture,
        recording=recording,
        single=single,
        dual=dual,
        preview=preview,
        controls=controls,
    )


def require_mapping(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"config.{key} must be a mapping")
    return value


def repo_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return REPO_ROOT / path


def positive_int(data: dict[str, Any], key: str, *, default: int | None = None) -> int:
    value = data.get(key, default)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a positive integer") from error
    if parsed <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return parsed


def positive_float(data: dict[str, Any], key: str, *, default: float | None = None) -> float:
    value = data.get(key, default)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a positive number") from error
    if parsed <= 0:
        raise ValueError(f"{key} must be a positive number")
    return parsed


def non_negative_float(data: dict[str, Any], key: str, *, default: float) -> float:
    value = data.get(key, default)
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{key} must be a non-negative number") from error
    if parsed < 0:
        raise ValueError(f"{key} must be a non-negative number")
    return parsed


def optional_positive_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("sample_fps must be a positive number or null") from error
    if parsed <= 0:
        raise ValueError("sample_fps must be a positive number or null")
    return parsed


def container_value(value: str) -> str:
    if value not in {"mkv", "mjpg"}:
        raise ValueError("recording.container must be mkv or mjpg")
    return value


def normalize_control_value(value: Any) -> ControlValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int | float):
        return value
    return str(value)


def format_control_value(value: ControlValue) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def safe_label(value: str) -> str:
    return "".join(character if character.isalnum() or character in "._-" else "_" for character in value)
