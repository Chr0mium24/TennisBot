from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Iterator

import cv2

from .config import CameraConfig, CameraSpec


@dataclass(frozen=True)
class CapturedFrame:
    camera_id: str
    sequence: int
    monotonic_ns: int
    unix_ns: int
    image: object


class FrameSource:
    def __init__(self, camera: CameraSpec, config: CameraConfig) -> None:
        self.camera = camera
        self.config = config
        self.capture = cv2.VideoCapture(camera.device, cv2.CAP_V4L2)
        spec = config.capture
        self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, spec.width)
        self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, spec.height)
        self.capture.set(cv2.CAP_PROP_FPS, spec.fps)
        self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*spec.pixel_format))
        if not self.capture.isOpened():
            self.capture.release()
            raise RuntimeError(f"cannot open {camera.camera_id}: {camera.device}")
        self.sequence = 0

    def read(self) -> CapturedFrame:
        ok, image = self.capture.read()
        monotonic_ns = time.monotonic_ns()
        unix_ns = time.time_ns()
        if not ok or image is None:
            raise RuntimeError(f"cannot read {self.camera.camera_id}: {self.camera.device}")
        frame = CapturedFrame(self.camera.camera_id, self.sequence, monotonic_ns, unix_ns, image)
        self.sequence += 1
        return frame

    def close(self) -> None:
        self.capture.release()

    def __enter__(self) -> "FrameSource":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


class StereoFrameSource:
    def __init__(self, left: CameraSpec, right: CameraSpec, config: CameraConfig) -> None:
        self.left = FrameSource(left, config)
        try:
            self.right = FrameSource(right, config)
        except Exception:
            self.left.close()
            raise
        self.pair_sequence = 0

    def read(self) -> tuple[int, CapturedFrame, CapturedFrame, int]:
        left = self.left.read()
        right = self.right.read()
        delta_ns = right.monotonic_ns - left.monotonic_ns
        pair = self.pair_sequence
        self.pair_sequence += 1
        return pair, left, right, delta_ns

    def close(self) -> None:
        self.left.close()
        self.right.close()

    def __enter__(self) -> "StereoFrameSource":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

