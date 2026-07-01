from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from camera_calib_lab.capture_types import CameraConfig, OpenCVCamera, preview_size
from camera_calib_lab.v4l2_controls import (
    AUTO_EXPOSURE_CONTROL,
    AUTO_EXPOSURE_VALUE,
    BRIGHTNESS_CONTROL,
    EXPOSURE_CONTROL,
    MANUAL_AUTO_EXPOSURE_VALUE,
    V4L2Control,
    control_payload,
    fallback_control,
    read_v4l2_controls,
    run_v4l2,
)


@dataclass(frozen=True)
class PreviewOptions:
    devices: list[str]
    width: int
    height: int
    fps: float
    fourcc: str
    exposure: int | None
    brightness: int | None
    auto_exposure: bool
    dry_run: bool
    max_width: int


@dataclass
class PreviewCamera:
    label: str
    device: str
    source: OpenCVCamera
    controls: "CameraControls"


class CameraControls:
    def __init__(
        self,
        *,
        device: str,
        label: str,
        exposure: int | None,
        brightness: int | None,
        auto_exposure: bool,
    ) -> None:
        self.device = device
        self.label = label
        self.auto_exposure = auto_exposure
        self.warning_keys: set[str] = set()
        controls = read_v4l2_controls(device)
        self.exposure = controls.get(EXPOSURE_CONTROL, fallback_control(EXPOSURE_CONTROL, 1, 2047, 1, 250))
        self.brightness = controls.get(BRIGHTNESS_CONTROL, fallback_control(BRIGHTNESS_CONTROL, -64, 64, 1, 0))
        default_exposure = self.exposure.value if self.auto_exposure else self.exposure.maximum
        self.exposure_value = self.exposure.clamp(exposure if exposure is not None else default_exposure)
        self.brightness_value = self.brightness.clamp(brightness if brightness is not None else self.brightness.maximum)
        self.applied_exposure: int | None = None
        self.applied_brightness: int | None = None

    def configure_initial(self) -> None:
        if self.auto_exposure:
            self.set_control(AUTO_EXPOSURE_CONTROL, AUTO_EXPOSURE_VALUE)
        else:
            self.set_control(AUTO_EXPOSURE_CONTROL, MANUAL_AUTO_EXPOSURE_VALUE)
            self.set_exposure(self.exposure_value)
        self.set_brightness(self.brightness_value)

    def create_trackbars(self, window_name: str) -> None:
        cv2.createTrackbar(
            self.exposure_trackbar,
            window_name,
            self.to_trackbar(self.exposure, self.exposure_value),
            self.trackbar_max(self.exposure),
            noop,
        )
        cv2.createTrackbar(
            self.brightness_trackbar,
            window_name,
            self.to_trackbar(self.brightness, self.brightness_value),
            self.trackbar_max(self.brightness),
            noop,
        )

    def update_from_trackbars(self, window_name: str) -> None:
        exposure_pos = cv2.getTrackbarPos(self.exposure_trackbar, window_name)
        brightness_pos = cv2.getTrackbarPos(self.brightness_trackbar, window_name)
        self.exposure_value = self.from_trackbar(self.exposure, exposure_pos)
        self.brightness_value = self.from_trackbar(self.brightness, brightness_pos)
        if not self.auto_exposure:
            self.set_exposure(self.exposure_value)
        self.set_brightness(self.brightness_value)

    @property
    def exposure_trackbar(self) -> str:
        return f"{self.label} shutter"

    @property
    def brightness_trackbar(self) -> str:
        return f"{self.label} brightness"

    def to_trackbar(self, control: V4L2Control, value: int) -> int:
        return max(0, min(self.trackbar_max(control), value - control.minimum))

    def from_trackbar(self, control: V4L2Control, position: int) -> int:
        value = control.minimum + position
        return control.clamp(value)

    def trackbar_max(self, control: V4L2Control) -> int:
        return max(1, control.maximum - control.minimum)

    def set_exposure(self, value: int) -> None:
        if self.applied_exposure == value:
            return
        self.applied_exposure = value
        self.set_control(EXPOSURE_CONTROL, value)

    def set_brightness(self, value: int) -> None:
        if self.applied_brightness == value:
            return
        self.applied_brightness = value
        self.set_control(BRIGHTNESS_CONTROL, value)

    def set_control(self, name: str, value: int) -> None:
        if not self.device.startswith("/dev/"):
            return
        result = run_v4l2(["-d", self.device, f"--set-ctrl={name}={value}"])
        if result["returncode"] == 0:
            return
        warning_key = f"{name}:{result['stderr']}"
        if warning_key in self.warning_keys:
            return
        self.warning_keys.add(warning_key)
        stderr = result["stderr"] or result["stdout"] or f"exit {result['returncode']}"
        print(f"warning: failed to set {name}={value} on {self.device}: {stderr}")

    def payload(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "label": self.label,
            "auto_exposure": self.auto_exposure,
            "exposure_time_absolute": control_payload(self.exposure, self.exposure_value),
            "brightness": control_payload(self.brightness, self.brightness_value),
        }


def run_camera_preview(options: PreviewOptions) -> dict[str, Any]:
    if options.dry_run:
        return dry_run_payload(options)

    if not options.devices:
        raise RuntimeError("camera preview requires at least one device")
    if len(options.devices) > 2:
        raise RuntimeError("camera preview supports one or two devices")

    config = CameraConfig(width_px=options.width, height_px=options.height, fps=options.fps, fourcc=options.fourcc)
    window_name = "TennisBot Camera Preview"
    cameras: list[PreviewCamera] = []
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    try:
        for index, device in enumerate(options.devices):
            label = camera_label(index, len(options.devices))
            controls = CameraControls(
                device=device,
                label=label,
                exposure=options.exposure,
                brightness=options.brightness,
                auto_exposure=options.auto_exposure,
            )
            controls.configure_initial()
            source = OpenCVCamera(device, config)
            controls.create_trackbars(window_name)
            cameras.append(PreviewCamera(label=label, device=device, source=source, controls=controls))

        while True:
            previews = []
            for camera in cameras:
                camera.controls.update_from_trackbars(window_name)
                frame = camera.source.read()
                previews.append(draw_preview_frame(frame, camera, max_width=options.max_width))
            cv2.imshow(window_name, combine_previews(previews))
            key = cv2.waitKey(30) & 0xFF
            if key in {27, ord("q"), ord("Q")}:
                break
    finally:
        for camera in cameras:
            camera.source.release()
        cv2.destroyWindow(window_name)

    return {"status": "closed", "devices": [camera.device for camera in cameras]}


def dry_run_payload(options: PreviewOptions) -> dict[str, Any]:
    cameras = []
    for index, device in enumerate(options.devices):
        controls = CameraControls(
            device=device,
            label=camera_label(index, len(options.devices)),
            exposure=options.exposure,
            brightness=options.brightness,
            auto_exposure=options.auto_exposure,
        )
        cameras.append(controls.payload())
    return {
        "status": "dry-run",
        "width": options.width,
        "height": options.height,
        "fps": options.fps,
        "fourcc": options.fourcc,
        "cameras": cameras,
        "keys": {"quit": "q or esc"},
    }


def draw_preview_frame(frame: np.ndarray, camera: PreviewCamera, *, max_width: int) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_gray = float(np.mean(gray))
    width, height = preview_size(frame, max_width=max_width)
    preview = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    lines = [
        f"{camera.label.upper()} {camera.device}",
        (
            f"shutter {camera.controls.exposure_value} | brightness {camera.controls.brightness_value}"
        ),
        f"mean {mean_gray:.1f} | q/esc quit",
    ]
    draw_preview_text(preview, lines)
    return preview


def draw_preview_text(preview: np.ndarray, lines: list[str]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = preview_text_scale(lines, preview.shape[1], font)
    thickness = max(2, int(round(scale * 2.0)))
    line_gap = max(34, int(round(scale * 38)))
    x = max(18, int(round(preview.shape[1] * 0.02)))
    for index, line in enumerate(lines):
        y = int(round(scale * 34)) + index * line_gap
        cv2.putText(preview, line, (x, y), font, scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
        cv2.putText(preview, line, (x, y), font, scale, (40, 255, 40), thickness, cv2.LINE_AA)


def preview_text_scale(lines: list[str], width: int, font: int) -> float:
    scale = max(0.95, min(1.2, width / 900.0))
    thickness = max(2, int(round(scale * 2.0)))
    available_width = max(1, width - 36)
    text_width = max((cv2.getTextSize(line, font, scale, thickness)[0][0] for line in lines), default=1)
    if text_width <= available_width:
        return scale
    return max(0.78, scale * (available_width / float(text_width)))


def combine_previews(previews: list[np.ndarray]) -> np.ndarray:
    if len(previews) == 1:
        return previews[0]
    height = min(preview.shape[0] for preview in previews)
    resized = [resize_to_height(preview, height) for preview in previews]
    return np.hstack(resized)


def resize_to_height(frame: np.ndarray, height: int) -> np.ndarray:
    current_height, current_width = frame.shape[:2]
    if current_height == height:
        return frame
    width = max(1, int(current_width * (height / float(current_height))))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def camera_label(index: int, total: int) -> str:
    if total == 1:
        return "cam"
    return "left" if index == 0 else "right"


def noop(_value: int) -> None:
    return None
