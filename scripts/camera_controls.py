#!/usr/bin/env python3

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Sequence

from process_utils import display_command, process_env


DEFAULT_CAMERA_CONTROLS: tuple[tuple[str, str], ...] = (
    ("brightness", "-5"),
    ("contrast", "1"),
    ("saturation", "64"),
    ("white_balance_automatic", "0"),
    ("white_balance_temperature", "4600"),
    ("gamma", "100"),
    ("gain", "32"),
    ("power_line_frequency", "1"),
    ("sharpness", "1"),
    ("backlight_compensation", "0"),
    ("auto_exposure", "1"),
    ("exposure_time_absolute", "10"),
    ("focus_automatic_continuous", "0"),
    ("focus_absolute", "0"),
)


def build_camera_control_commands(devices: Sequence[str]) -> list[list[str]]:
    return [
        ["v4l2-ctl", "-d", device, f"--set-ctrl={name}={value}"]
        for device in devices
        for name, value in DEFAULT_CAMERA_CONTROLS
    ]


def display_camera_control_command(command: Sequence[str]) -> str:
    return display_command(command)


def apply_default_camera_controls(devices: Sequence[str], cwd: Path) -> None:
    for command in build_camera_control_commands(devices):
        result = subprocess.run(command, cwd=cwd, env=process_env(), check=False)
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to apply camera controls: {display_camera_control_command(command)}"
            )
