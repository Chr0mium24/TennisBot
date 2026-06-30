from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from camera_calib_lab.capture_gui import CameraConfig, OpenCVCamera, preview_size


EXPOSURE_CONTROL = "exposure_time_absolute"
GAIN_CONTROL = "gain"
BRIGHTNESS_CONTROL = "brightness"
AUTO_EXPOSURE_CONTROL = "auto_exposure"
MANUAL_AUTO_EXPOSURE_VALUE = 1
AUTO_EXPOSURE_VALUE = 3


@dataclass(frozen=True)
class V4L2Control:
    name: str
    minimum: int
    maximum: int
    step: int
    default: int
    value: int
    available: bool = True

    def clamp(self, value: int) -> int:
        clamped = max(self.minimum, min(self.maximum, int(value)))
        if self.step <= 1:
            return clamped
        return self.minimum + ((clamped - self.minimum) // self.step) * self.step


@dataclass(frozen=True)
class PreviewOptions:
    devices: list[str]
    width: int
    height: int
    fps: float
    fourcc: str
    exposure: int | None
    gain: int | None
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
        gain: int | None,
        brightness: int | None,
        auto_exposure: bool,
    ) -> None:
        self.device = device
        self.label = label
        self.auto_exposure = auto_exposure
        self.warning_keys: set[str] = set()
        controls = read_v4l2_controls(device)
        self.exposure = controls.get(EXPOSURE_CONTROL, fallback_control(EXPOSURE_CONTROL, 1, 2047, 1, 250))
        self.gain = controls.get(GAIN_CONTROL, fallback_control(GAIN_CONTROL, 0, 255, 1, 64))
        self.brightness = controls.get(BRIGHTNESS_CONTROL, fallback_control(BRIGHTNESS_CONTROL, -64, 64, 1, 0))
        default_exposure = self.exposure.value if self.auto_exposure else self.exposure.maximum
        self.exposure_value = self.exposure.clamp(exposure if exposure is not None else default_exposure)
        self.gain_value = self.gain.clamp(gain if gain is not None else self.gain.maximum)
        self.brightness_value = self.brightness.clamp(brightness if brightness is not None else self.brightness.maximum)
        self.applied_exposure: int | None = None
        self.applied_gain: int | None = None
        self.applied_brightness: int | None = None

    def configure_initial(self) -> None:
        if self.auto_exposure:
            self.set_control(AUTO_EXPOSURE_CONTROL, AUTO_EXPOSURE_VALUE)
        else:
            self.set_control(AUTO_EXPOSURE_CONTROL, MANUAL_AUTO_EXPOSURE_VALUE)
            self.set_exposure(self.exposure_value)
        self.set_gain(self.gain_value)
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
            self.gain_trackbar,
            window_name,
            self.to_trackbar(self.gain, self.gain_value),
            self.trackbar_max(self.gain),
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
        gain_pos = cv2.getTrackbarPos(self.gain_trackbar, window_name)
        brightness_pos = cv2.getTrackbarPos(self.brightness_trackbar, window_name)
        self.exposure_value = self.from_trackbar(self.exposure, exposure_pos)
        self.gain_value = self.from_trackbar(self.gain, gain_pos)
        self.brightness_value = self.from_trackbar(self.brightness, brightness_pos)
        if not self.auto_exposure:
            self.set_exposure(self.exposure_value)
        self.set_gain(self.gain_value)
        self.set_brightness(self.brightness_value)

    @property
    def exposure_trackbar(self) -> str:
        return f"{self.label} shutter"

    @property
    def gain_trackbar(self) -> str:
        return f"{self.label} gain"

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

    def set_gain(self, value: int) -> None:
        if self.applied_gain == value:
            return
        self.applied_gain = value
        self.set_control(GAIN_CONTROL, value)

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
            "gain": control_payload(self.gain, self.gain_value),
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
                gain=options.gain,
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
            gain=options.gain,
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
    preview = frame.copy()
    lines = [
        f"{camera.label} {camera.device}",
        (
            f"shutter={camera.controls.exposure_value} gain={camera.controls.gain_value} "
            f"brightness={camera.controls.brightness_value} mean={mean_gray:.1f}"
        ),
        "trackbars: shutter/gain/brightness  q/esc: quit",
    ]
    for index, line in enumerate(lines):
        y = 28 + index * 26
        cv2.putText(preview, line, (18, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 220, 20), 2, cv2.LINE_AA)
    width, height = preview_size(preview, max_width=max_width)
    return cv2.resize(preview, (width, height), interpolation=cv2.INTER_AREA)


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


def read_v4l2_controls(device: str) -> dict[str, V4L2Control]:
    result = run_v4l2(["-d", device, "--list-ctrls"])
    if result["returncode"] != 0:
        return {}
    controls: dict[str, V4L2Control] = {}
    for line in result["stdout"].splitlines():
        parsed = parse_control_line(line)
        if parsed is not None:
            controls[parsed.name] = parsed
    return controls


def parse_control_line(line: str) -> V4L2Control | None:
    match = re.match(r"\s*(?P<name>[A-Za-z0-9_]+)\s+.*:\s+(?P<body>.+)$", line)
    if match is None:
        return None
    body = match.group("body")
    values = {key: int(value) for key, value in re.findall(r"(min|max|step|default|value)=(-?\d+)", body)}
    if not {"min", "max", "default", "value"}.issubset(values):
        return None
    step = max(1, values.get("step", 1))
    return V4L2Control(
        name=match.group("name"),
        minimum=values["min"],
        maximum=values["max"],
        step=step,
        default=values["default"],
        value=values["value"],
    )


def fallback_control(name: str, minimum: int, maximum: int, step: int, default: int) -> V4L2Control:
    return V4L2Control(name=name, minimum=minimum, maximum=maximum, step=step, default=default, value=default, available=False)


def control_payload(control: V4L2Control, selected_value: int) -> dict[str, Any]:
    return {
        "available": control.available,
        "min": control.minimum,
        "max": control.maximum,
        "step": control.step,
        "default": control.default,
        "current": control.value,
        "selected": selected_value,
    }


def run_v4l2(args: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["v4l2-ctl", *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "v4l2-ctl not found"}
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def camera_label(index: int, total: int) -> str:
    if total == 1:
        return "cam"
    return "left" if index == 0 else "right"


def noop(_value: int) -> None:
    return None
