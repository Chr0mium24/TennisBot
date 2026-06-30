from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BrightnessOptions:
    devices: list[str] | None
    width: int
    height: int
    fps: int
    input_format: str
    timeout_ms: int
    json_output: bool
    dry_run: bool


def run_camera_brightness_check(options: BrightnessOptions) -> tuple[dict[str, Any], int]:
    selected_devices = options.devices or [device["device"] for device in list_capture_devices()[:2]]
    selected_devices = selected_devices[:2]
    if options.dry_run:
        devices = [
            {
                "device": device,
                **read_device_info(device),
                "average_brightness": None,
                "sample_bytes": 0,
                "status": "dry-run",
            }
            for device in selected_devices
        ]
    else:
        devices = [measure_device(device, options) for device in selected_devices]
    ok_devices = [device for device in devices if isinstance(device["average_brightness"], (int, float))]
    darkest = sorted(ok_devices, key=lambda device: float(device["average_brightness"]))[0] if ok_devices else None
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "devices": devices,
        "darkest_device": darkest["device"] if darkest else None,
        "command_hints": command_hints(devices),
    }
    return report, 0 if len(ok_devices) >= 2 or options.dry_run else 1


def print_brightness_report(report: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    print("Camera brightness check:")
    devices = report.get("devices", [])
    if not devices:
        print("- no V4L2 capture devices found")
        return
    for device in devices:
        brightness = device.get("average_brightness")
        value = "failed" if brightness is None else f"{float(brightness):.2f} / 255"
        print(f"- {device.get('device')}: {value}")
        print(f"  card: {device.get('card', 'unknown')}")
        print(f"  bus: {device.get('bus', 'unknown')}")
        if device.get("status") == "dry-run":
            print("  status: dry-run")
        if device.get("error") is not None:
            print(f"  error: {device['error']}")
    if report.get("darkest_device") is not None:
        print("")
        print(f"Darkest camera candidate: {report['darkest_device']}")
        print("If one lens cap is still on, it is probably the device with the lower average brightness.")
    hints = report.get("command_hints", [])
    if hints:
        print("")
        print("Command hints using the measured order:")
        for hint in hints:
            print(f"- {hint}")


def list_capture_devices() -> list[dict[str, str]]:
    dev = Path("/dev")
    if not dev.exists():
        return []
    devices = []
    for path in sorted(dev.iterdir(), key=lambda item: video_device_sort_key(item.name)):
        if not re.fullmatch(r"video\d+", path.name):
            continue
        device = f"/dev/{path.name}"
        info = read_device_info(device)
        if device_has_capture_capability(device) and "usb" in info["bus"].lower():
            devices.append({"device": device, **info})
    return devices


def measure_device(device: str, options: BrightnessOptions) -> dict[str, Any]:
    info = read_device_info(device)
    attempts = [options.input_format, ""] if options.input_format else [""]
    last_error = "capture failed"
    for input_format in attempts:
        result = capture_gray_frame(device, options, input_format=input_format)
        if result["ok"]:
            return {
                "device": device,
                **info,
                "average_brightness": result["average"],
                "sample_bytes": result["bytes"],
                "status": "ok",
            }
        last_error = str(result["error"])
    return {
        "device": device,
        **info,
        "average_brightness": None,
        "sample_bytes": 0,
        "status": "failed",
        "error": last_error,
    }


def capture_gray_frame(device: str, options: BrightnessOptions, *, input_format: str) -> dict[str, Any]:
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "v4l2",
        *([] if input_format == "" else ["-input_format", input_format]),
        "-video_size",
        f"{options.width}x{options.height}",
        "-framerate",
        str(options.fps),
        "-i",
        device,
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=options.timeout_ms / 1000,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"ffmpeg timed out after {options.timeout_ms} ms"}
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.decode("utf-8", errors="replace").strip() or f"ffmpeg exited {result.returncode}"}
    if len(result.stdout) == 0:
        return {"ok": False, "error": "ffmpeg produced no frame bytes"}
    average = round(sum(result.stdout) / len(result.stdout), 2)
    return {"ok": True, "average": average, "bytes": len(result.stdout)}


def read_device_info(device: str) -> dict[str, str]:
    result = subprocess.run(["v4l2-ctl", "-D", "-d", device], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    text = result.stdout.decode("utf-8", errors="replace")
    return {
        "card": value_after_colon(text, "Card type") or "unknown",
        "bus": value_after_colon(text, "Bus info") or "unknown",
    }


def device_has_capture_capability(device: str) -> bool:
    result = subprocess.run(["v4l2-ctl", "-D", "-d", device], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return result.returncode == 0 and "Video Capture" in result.stdout.decode("utf-8", errors="replace")


def value_after_colon(text: str, label: str) -> str | None:
    for line in text.splitlines():
        if label not in line:
            continue
        _prefix, separator, value = line.partition(":")
        if separator == "":
            return None
        return value.strip() or None
    return None


def command_hints(devices: list[dict[str, Any]]) -> list[str]:
    ok = [device for device in devices if device.get("status") in {"ok", "dry-run"}]
    if len(ok) < 2:
        return []
    left, right = ok[:2]
    return [
        f"calibration stereo: --left-device {left['device']} --right-device {right['device']}",
        f"Live3D hardware verifier: --uvc-devices {left['device']},{right['device']}",
    ]


def video_device_sort_key(name: str) -> tuple[int, str]:
    match = re.fullmatch(r"video(\d+)", name)
    return (int(match.group(1)), name) if match else (10**9, name)
