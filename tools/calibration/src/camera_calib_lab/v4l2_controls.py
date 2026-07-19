from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable

from tennisbot_camera.config import load_camera_config


EXPOSURE_CONTROL = "exposure_time_absolute"
BRIGHTNESS_CONTROL = "brightness"
GAIN_CONTROL = "gain"
AUTO_EXPOSURE_CONTROL = "auto_exposure"
MANUAL_AUTO_EXPOSURE_VALUE = 1
AUTO_EXPOSURE_VALUE = 3
CALIBRATION_CONTROL_NAMES = (
    AUTO_EXPOSURE_CONTROL,
    EXPOSURE_CONTROL,
    BRIGHTNESS_CONTROL,
    GAIN_CONTROL,
    "white_balance_automatic",
    "white_balance_temperature",
    "focus_automatic_continuous",
    "focus_absolute",
)
_CAPTURE_PROFILE = load_camera_config().profile("calibration")
CALIBRATION_CAPTURE_CONTROL_VALUES = tuple(
    (name, _CAPTURE_PROFILE[name])
    for name in (
        AUTO_EXPOSURE_CONTROL,
        EXPOSURE_CONTROL,
        "white_balance_automatic",
        "white_balance_temperature",
        "focus_automatic_continuous",
        "focus_absolute",
    )
)


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


def v4l2_controls_snapshot(
    device: str | int,
    control_names: Iterable[str] = CALIBRATION_CONTROL_NAMES,
) -> dict[str, Any]:
    controls = read_v4l2_controls(str(device))
    return {name: control_readback_payload(controls[name]) for name in control_names if name in controls}


def camera_controls_report(devices: Iterable[str]) -> str:
    lines = ["Current V4L2 camera controls:"]
    for device in devices:
        controls = read_v4l2_controls(str(device))
        lines.append(f"- {device}:")
        for name in CALIBRATION_CONTROL_NAMES:
            control = controls.get(name)
            if control is None:
                lines.append(f"  {name}: unsupported")
                continue
            lines.append(f"  {name}: {control.value}{control_mode_label(name, control.value)}")
    return "\n".join(lines)


def apply_calibration_capture_controls(devices: Iterable[str]) -> str:
    lines = ["Applied calibration camera controls:"]
    for device in devices:
        controls = read_v4l2_controls(str(device))
        missing = [name for name, _ in CALIBRATION_CAPTURE_CONTROL_VALUES if name not in controls]
        if missing:
            raise RuntimeError(f"{device} does not provide required controls: {', '.join(missing)}")
        for name, value in CALIBRATION_CAPTURE_CONTROL_VALUES:
            result = run_v4l2(["-d", str(device), f"--set-ctrl={name}={value}"])
            if result["returncode"] != 0:
                detail = result["stderr"] or result["stdout"] or "unknown v4l2-ctl error"
                raise RuntimeError(f"failed to set {device} {name}={value}: {detail}")
        lines.append(f"- {device}: exposure=10 manual, focus=600 manual, white_balance=4600 manual")
    return "\n".join(lines)


def control_mode_label(name: str, value: int) -> str:
    if name == AUTO_EXPOSURE_CONTROL:
        if value == MANUAL_AUTO_EXPOSURE_VALUE:
            return " (manual)"
        if value == AUTO_EXPOSURE_VALUE:
            return " (auto)"
    if name in {"focus_automatic_continuous", "white_balance_automatic"}:
        return " (auto)" if value else " (manual)"
    return ""


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
    values = {
        key: int(value)
        for key, value in re.findall(r"(min|max|step|default|value)=(-?\d+)", body)
    }
    if "(bool)" in line:
        values.setdefault("min", 0)
        values.setdefault("max", 1)
        values.setdefault("step", 1)
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
    return V4L2Control(
        name=name,
        minimum=minimum,
        maximum=maximum,
        step=step,
        default=default,
        value=default,
        available=False,
    )


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


def control_readback_payload(control: V4L2Control) -> dict[str, Any]:
    return {
        "available": control.available,
        "min": control.minimum,
        "max": control.maximum,
        "step": control.step,
        "default": control.default,
        "current": control.value,
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
