from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path
from typing import Mapping

import yaml


@dataclass(frozen=True)
class CameraSpec:
    camera_id: str
    role: str
    device: str


@dataclass(frozen=True)
class CaptureSpec:
    width: int
    height: int
    fps: float
    pixel_format: str


@dataclass(frozen=True)
class CameraConfig:
    capture: CaptureSpec
    cameras: Mapping[str, CameraSpec]
    profiles: Mapping[str, Mapping[str, int]]

    def camera(self, camera_id: str) -> CameraSpec:
        try:
            return self.cameras[camera_id]
        except KeyError as error:
            raise ValueError(f"unknown camera: {camera_id}") from error

    def devices(self, target: str) -> tuple[CameraSpec, ...]:
        if target == "stereo":
            return (self.camera("cam1"), self.camera("cam2"))
        return (self.camera(target),)

    def profile(self, name: str) -> Mapping[str, int]:
        try:
            return self.profiles[name]
        except KeyError as error:
            raise ValueError(f"unknown camera profile: {name}") from error


def load_camera_config(path: Path | None = None) -> CameraConfig:
    source = path or Path(str(files("tennisbot_camera").joinpath("camera_config.yaml")))
    payload = yaml.safe_load(source.read_text(encoding="utf-8"))
    capture = payload["capture"]
    cameras = {
        camera_id: CameraSpec(camera_id, item["role"], item["device"])
        for camera_id, item in payload["cameras"].items()
    }
    profiles = {
        name: {key: int(value) for key, value in values.items()}
        for name, values in payload["profiles"].items()
    }
    return CameraConfig(
        capture=CaptureSpec(
            width=int(capture["width"]),
            height=int(capture["height"]),
            fps=float(capture["fps"]),
            pixel_format=str(capture["pixel_format"]),
        ),
        cameras=cameras,
        profiles=profiles,
    )

