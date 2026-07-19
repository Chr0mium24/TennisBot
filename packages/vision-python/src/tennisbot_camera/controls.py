from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Mapping, Sequence


def control_string(controls: Mapping[str, int]) -> str:
    return ",".join(f"{name}={value}" for name, value in controls.items())


def apply_command(device: str, controls: Mapping[str, int]) -> list[str]:
    return ["v4l2-ctl", "-d", device, f"--set-ctrl={control_string(controls)}"]


def show_command(device: str) -> list[str]:
    return ["v4l2-ctl", "-d", device, "--all"]


def run_command(command: Sequence[str], *, dry_run: bool = False) -> subprocess.CompletedProcess[str] | None:
    if dry_run:
        print(" ".join(command))
        return None
    return subprocess.run(command, check=False, text=True, capture_output=True)


def stable_aliases(device: Path) -> list[str]:
    by_id = Path("/dev/v4l/by-id")
    if not by_id.exists():
        return []
    resolved = device.resolve()
    return sorted(str(item) for item in by_id.iterdir() if item.resolve() == resolved)


def report_payload(camera_id: str, device: str, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    return {
        "camera_id": camera_id,
        "device": device,
        "ok": result.returncode == 0,
        "controls": result.stdout,
        "error": result.stderr.strip() or None,
    }


def print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))

