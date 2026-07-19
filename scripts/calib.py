#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from os import path as os_path
from pathlib import Path

from process_utils import (
    REPO_ROOT,
    has_any_option,
    require_value,
    run_streaming,
    shell_quote,
)


CALIBRATION_CWD = REPO_ROOT / "tools/calibration"
CALIBRATION_COMMAND = ["uv", "run", "camera-calib-lab"]
CameraId = str
Mode = str


@dataclass
class MonoOptions:
    camera_id: CameraId
    mode: Mode
    dry_run: bool
    run_id: str
    device: str
    views: str
    output: Path
    config: Path
    min_views: str
    max_rms_px: str
    session: Path | None = None


@dataclass
class StereoOptions:
    mode: Mode
    dry_run: bool
    run_id: str
    left_device: str
    right_device: str
    views: str
    output: Path
    config: Path
    min_pairs: str
    max_rms_px: str
    session: Path | None = None
    left_mono: Path | None = None
    right_mono: Path | None = None


@dataclass
class CommandStep:
    label: str
    args: list[str]


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h"}:
        print_usage()
        return 0

    try:
        workflow = argv[0]
        if workflow not in {"online", "offline"}:
            raise ValueError(f"Unknown calibration workflow: {workflow}")
        if len(argv) < 2 or argv[1] in {"--help", "-h"}:
            print_usage()
            return 0
        kind = argv[1]
        rest = argv[2:]
        if kind not in {"mono", "stereo"}:
            raise ValueError("calibration kind must be mono or stereo")
        if has_any_option(rest, ["--capture-only", "--solve-only"]):
            raise ValueError("capture-only/solve-only are internal; use online or offline")
        if workflow == "offline":
            if not has_any_option(rest, ["--session"]):
                raise ValueError("offline calibration requires --session <path>")
            rest = [*rest, "--solve-only"]
        if kind == "mono":
            return run_mono(rest)
        return run_stereo(rest)
    except ValueError as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_usage()
        return 2


def run_mono(args: list[str]) -> int:
    options = parse_mono_options(args)
    session = options.session or default_session_path(
        options.mode,
        f"{options.camera_id}_charuco",
        options.run_id,
    )
    steps: list[CommandStep] = []
    if options.mode != "solve-only":
        if options.mode == "capture-solve" and session.exists():
            raise ValueError(
                f"Session path already exists: {session}. Pass --session to a new path or use --solve-only."
            )
        steps.append(
            CommandStep(
                f"{options.camera_id} prepare controls",
                ["@camera", "controls", "apply", options.camera_id, "--profile", "calibration"],
            )
        )
        steps.append(
            CommandStep(
                f"{options.camera_id} current controls",
                ["@camera", "controls", "show", options.camera_id],
            )
        )
        steps.append(
            CommandStep(
                f"{options.camera_id} capture",
                [
                    "capture",
                    "charuco-auto-gui",
                    "--config",
                    str(options.config),
                    "--device",
                    options.device,
                    "--camera-id",
                    options.camera_id,
                    "--views",
                    options.views,
                    "--output",
                    str(session),
                ],
            )
        )
    if options.mode != "capture-only":
        steps.append(
            CommandStep(
                f"{options.camera_id} solve",
                [
                    "solve",
                    "mono",
                    "--config",
                    str(options.config),
                    "--session",
                    str(session),
                    "--output",
                    str(options.output),
                    "--camera-id",
                    options.camera_id,
                    "--min-views",
                    options.min_views,
                    "--max-rms-px",
                    options.max_rms_px,
                ],
            )
        )
    return run_steps(steps, options.dry_run)


def run_stereo(args: list[str]) -> int:
    options = parse_stereo_options(args)
    session = options.session or default_session_path(options.mode, "stereo_charuco", options.run_id)
    steps: list[CommandStep] = []
    left_mono: Path | None = None
    right_mono: Path | None = None
    if options.mode != "capture-only":
        left_mono = options.left_mono or latest_mono_artifact_path("cam1")
        right_mono = options.right_mono or latest_mono_artifact_path("cam2")
        print("Stereo mono calibration inputs:")
        print(f"  cam1: {display_path(left_mono)}")
        print(f"  cam2: {display_path(right_mono)}")
    if options.mode != "solve-only":
        if options.mode == "capture-solve" and session.exists():
            raise ValueError(
                f"Session path already exists: {session}. Pass --session to a new path or use --solve-only."
            )
        steps.append(
            CommandStep(
                "stereo prepare controls",
                ["@camera", "controls", "apply", "stereo", "--profile", "calibration"],
            )
        )
        steps.append(
            CommandStep(
                "stereo current controls",
                ["@camera", "controls", "show", "stereo"],
            )
        )
        steps.append(
            CommandStep(
                "stereo capture",
                [
                    "capture",
                    "stereo-charuco-auto-gui",
                    "--config",
                    str(options.config),
                    "--left-device",
                    options.left_device,
                    "--right-device",
                    options.right_device,
                    "--views",
                    options.views,
                    "--output",
                    str(session),
                ],
            )
        )
    if options.mode != "capture-only":
        assert left_mono is not None
        assert right_mono is not None
        steps.append(
            CommandStep(
                "stereo solve",
                [
                    "solve",
                    "stereo",
                    "--config",
                    str(options.config),
                    "--session",
                    str(session),
                    "--left-mono",
                    str(left_mono),
                    "--right-mono",
                    str(right_mono),
                    "--output",
                    str(options.output),
                    "--left-camera-id",
                    "cam1",
                    "--right-camera-id",
                    "cam2",
                    "--min-pairs",
                    options.min_pairs,
                    "--max-rms-px",
                    options.max_rms_px,
                ],
            )
        )
    return run_steps(steps, options.dry_run)


def run_steps(steps: list[CommandStep], dry_run: bool) -> int:
    for step in steps:
        code = run_step(step, dry_run)
        if code != 0:
            return code
    return 0


def run_step(step: CommandStep, dry_run: bool) -> int:
    is_camera = bool(step.args and step.args[0] == "@camera")
    command = (
        ["uv", "run", str(REPO_ROOT / "scripts/camera.py"), *step.args[1:]]
        if is_camera
        else [*CALIBRATION_COMMAND, *step.args]
    )
    cwd = REPO_ROOT if is_camera else CALIBRATION_CWD
    if dry_run:
        print(f"{step.label}:")
        print(f"  cd {display_path(cwd)}")
        print(f"  {display_calibration_command(command) if not is_camera else ' '.join(shell_quote(value) for value in command)}")
        return 0
    return run_streaming(command, cwd=cwd)


def parse_mono_options(args: list[str]) -> MonoOptions:
    if not args or args[0] in {"--help", "-h"}:
        print_mono_usage()
        raise SystemExit(0)
    camera_id = parse_camera_id(args[0])
    run_id = timestamp()
    parsed = MonoOptions(
        camera_id=camera_id,
        mode="capture-solve",
        dry_run=False,
        run_id=run_id,
        device="/dev/video0" if camera_id == "cam1" else "/dev/video2",
        views="30",
        output=default_artifact_output_path(camera_id, run_id),
        config=config_path(),
        min_views="8",
        max_rms_px="1.0",
    )
    index = 1
    while index < len(args):
        arg = args[index]
        if arg == "--capture-only":
            parsed.mode = set_mode(parsed.mode, "capture-only")
        elif arg == "--solve-only":
            parsed.mode = set_mode(parsed.mode, "solve-only")
        elif arg == "--dry-run":
            parsed.dry_run = True
        elif arg == "--device":
            index += 1
            parsed.device = require_value(args, index, arg)
        elif arg == "--views":
            index += 1
            parsed.views = require_positive_integer(args, index, arg)
        elif arg == "--session":
            index += 1
            parsed.session = path_from_repo(require_value(args, index, arg))
        elif arg == "--output":
            index += 1
            parsed.output = path_from_repo(require_value(args, index, arg))
        elif arg == "--config":
            index += 1
            parsed.config = path_from_repo(require_value(args, index, arg))
        elif arg == "--min-views":
            index += 1
            parsed.min_views = require_positive_integer(args, index, arg)
        elif arg == "--max-rms-px":
            index += 1
            parsed.max_rms_px = require_positive_number(args, index, arg)
        else:
            raise ValueError(f"Unknown mono option: {arg}")
        index += 1
    return parsed


def parse_stereo_options(args: list[str]) -> StereoOptions:
    if args and args[0] in {"--help", "-h"}:
        print_stereo_usage()
        raise SystemExit(0)
    run_id = timestamp()
    parsed = StereoOptions(
        mode="capture-solve",
        dry_run=False,
        run_id=run_id,
        left_device="/dev/video0",
        right_device="/dev/video2",
        views="30",
        output=default_artifact_output_path("stereo_cam1_cam2", run_id),
        config=config_path(),
        min_pairs="12",
        max_rms_px="2.0",
    )
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--capture-only":
            parsed.mode = set_mode(parsed.mode, "capture-only")
        elif arg == "--solve-only":
            parsed.mode = set_mode(parsed.mode, "solve-only")
        elif arg == "--dry-run":
            parsed.dry_run = True
        elif arg == "--devices":
            index += 1
            devices = require_value(args, index, arg).split(",")
            if len(devices) < 2 or not devices[0] or not devices[1]:
                raise ValueError("--devices requires <left,right>")
            parsed.left_device = devices[0]
            parsed.right_device = devices[1]
        elif arg == "--left-device":
            index += 1
            parsed.left_device = require_value(args, index, arg)
        elif arg == "--right-device":
            index += 1
            parsed.right_device = require_value(args, index, arg)
        elif arg == "--views":
            index += 1
            parsed.views = require_positive_integer(args, index, arg)
        elif arg == "--session":
            index += 1
            parsed.session = path_from_repo(require_value(args, index, arg))
        elif arg == "--output":
            index += 1
            parsed.output = path_from_repo(require_value(args, index, arg))
        elif arg == "--left-mono":
            index += 1
            parsed.left_mono = path_from_repo(require_value(args, index, arg))
        elif arg == "--right-mono":
            index += 1
            parsed.right_mono = path_from_repo(require_value(args, index, arg))
        elif arg == "--config":
            index += 1
            parsed.config = path_from_repo(require_value(args, index, arg))
        elif arg == "--min-pairs":
            index += 1
            parsed.min_pairs = require_positive_integer(args, index, arg)
        elif arg == "--max-rms-px":
            index += 1
            parsed.max_rms_px = require_positive_number(args, index, arg)
        else:
            raise ValueError(f"Unknown stereo option: {arg}")
        index += 1
    return parsed


def brightness_args(args: list[str]) -> list[str]:
    has_device_override = any(arg == "--devices" or arg.startswith("--devices=") for arg in args)
    if "--help" in args or "-h" in args or has_device_override:
        return args
    return ["--devices", "/dev/video0,/dev/video2", *args]


def preview_args(args: list[str]) -> list[str]:
    target = args[0] if args else None
    rest = args[1:] if args else []
    if target == "cam1":
        return preview_mono_args("/dev/video0", rest)
    if target == "cam2":
        return preview_mono_args("/dev/video2", rest)
    if target == "stereo":
        return preview_stereo_args(rest)
    if target is not None and not target.startswith("-"):
        raise ValueError(f"Unknown preview target: {target}. Use cam1, cam2, or stereo.")
    return preview_stereo_args(args)


def preview_mono_args(default_device: str, args: list[str]) -> list[str]:
    if has_any_option(args, ["--device", "--devices"]):
        return args
    return ["--device", default_device, *args]


def preview_stereo_args(args: list[str]) -> list[str]:
    if has_any_option(args, ["--device", "--devices"]):
        return args
    return ["--devices", "/dev/video0,/dev/video2", *args]


def default_session_path(mode: Mode, prefix: str, run_id: str) -> Path:
    if mode == "solve-only":
        return latest_session_path(prefix)
    return unique_path(CALIBRATION_CWD / "captures/local" / f"{prefix}_{run_id}")


def latest_session_path(prefix: str) -> Path:
    directory = CALIBRATION_CWD / "captures/local"
    if not directory.exists():
        raise ValueError(f"No captures directory found at {directory}; pass --session for --solve-only.")
    candidates = [
        path
        for path in directory.iterdir()
        if path.name.startswith(prefix) and (path / "manifest.json").exists()
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    if not candidates:
        raise ValueError(f"No capture session found for prefix {prefix}; pass --session for --solve-only.")
    return candidates[0]


def set_mode(current: Mode, next_mode: Mode) -> Mode:
    if current != "capture-solve" and current != next_mode:
        raise ValueError("--capture-only and --solve-only are mutually exclusive")
    return next_mode


def parse_camera_id(value: str) -> CameraId:
    if value in {"cam1", "cam2"}:
        return value
    raise ValueError("mono requires camera id cam1 or cam2")


def require_positive_integer(args: list[str], index: int, flag: str) -> str:
    value = require_value(args, index, flag)
    if not value.isdigit() or int(value) <= 0:
        raise ValueError(f"{flag} must be a positive integer")
    return value


def require_positive_number(args: list[str], index: int, flag: str) -> str:
    value = require_value(args, index, flag)
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"{flag} must be a positive number") from error
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{flag} must be a positive number")
    return value


def config_path() -> Path:
    return CALIBRATION_CWD / "configs/dfoptix_charuco_15mm_capture.yaml"


def artifact_path(name: str) -> Path:
    return REPO_ROOT / "artifacts/calibration" / name


def default_artifact_output_path(name: str, run_id: str) -> Path:
    return unique_path(artifact_path(f"{name}_{run_id}"))


def latest_mono_artifact_path(camera_id: CameraId) -> Path:
    directory = REPO_ROOT / "artifacts/calibration"
    if not directory.exists():
        raise ValueError(
            f"No calibration artifact directory found at {directory}; pass --left-mono/--right-mono explicitly."
        )
    candidates = [path for path in directory.iterdir() if is_accepted_mono_artifact(path, camera_id)]
    candidates.sort(
        key=lambda path: (artifact_created_at_ms(path), path.stat().st_mtime * 1000),
        reverse=True,
    )
    if not candidates:
        raise ValueError(
            f"No accepted mono calibration package found for {camera_id}; run mono {camera_id} first or pass --left-mono/--right-mono."
        )
    return candidates[0]


def is_accepted_mono_artifact(path: Path, camera_id: CameraId) -> bool:
    if not path.is_dir():
        return False
    package_json = read_package_json(path)
    return (
        package_json is not None
        and package_json.get("schema_version") == "calibration.mono.v1"
        and package_json.get("package_type") == "mono_camera_calibration"
        and package_json.get("camera_id") == camera_id
        and package_json.get("accepted") is True
    )


def artifact_created_at_ms(path: Path) -> float:
    package_json = read_package_json(path)
    created_at = package_json.get("created_at") if package_json else None
    if isinstance(created_at, str):
        try:
            return datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp() * 1000
        except ValueError:
            pass
    return path.stat().st_mtime * 1000


def read_package_json(path: Path) -> dict[str, object] | None:
    try:
        payload = json.loads((path / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    suffix = 2
    while True:
        candidate = Path(f"{path}_{suffix}")
        if not candidate.exists():
            return candidate
        suffix += 1


def path_from_repo(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def timestamp() -> str:
    now = datetime.now().astimezone()
    timezone = local_time_zone_abbreviation(now)
    return now.strftime(f"%Y%m%d_%H%M%S_{timezone}")


def local_time_zone_abbreviation(date: datetime) -> str:
    timezone = date.tzname()
    if timezone:
        if timezone.isalnum() and len(timezone) > 1:
            return timezone
        abbreviation = "".join(word[:1] for word in timezone.split())
        abbreviation = "".join(ch for ch in abbreviation if ch.isalnum())
        if abbreviation:
            return abbreviation
    offset = date.utcoffset()
    if offset is None:
        return "UTCp0000"
    total_minutes = round(offset.total_seconds() / 60)
    sign = "p" if total_minutes >= 0 else "m"
    absolute_minutes = abs(total_minutes)
    hours = absolute_minutes // 60
    minutes = absolute_minutes % 60
    return f"UTC{sign}{hours:02d}{minutes:02d}"


def display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(REPO_ROOT))
    except ValueError:
        return str(resolved)


def display_calibration_command(command: list[str]) -> str:
    return " ".join(shell_quote(display_command_arg(value)) for value in command)


def display_command_arg(value: str) -> str:
    if not value.startswith("/"):
        return value
    resolved = Path(value).resolve()
    try:
        relative = resolved.relative_to(CALIBRATION_CWD)
        return str(relative) or "."
    except ValueError:
        pass
    try:
        resolved.relative_to(REPO_ROOT)
        return os_path.relpath(resolved, CALIBRATION_CWD)
    except ValueError:
        return value


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/calib.py online mono cam1 [options]
  uv run scripts/calib.py online mono cam2 [options]
  uv run scripts/calib.py online stereo [options]
  uv run scripts/calib.py offline mono cam1 --session <path> [options]
  uv run scripts/calib.py offline mono cam2 --session <path> [options]
  uv run scripts/calib.py offline stereo --session <path> [options]

online 会应用 calibration 控制配置，打开 ChArUco GUI 采集，然后求解并导出。
offline 只读取指定 session 求解，不打开相机或 GUI。
亮度检查、原始预览和控制配置请使用 scripts/camera.py。

通用选项:
  --session <path>  online 可指定输出 session；offline 必须指定输入 session
  --output <path>   标定包输出路径
  --dry-run         只打印步骤
"""
    )


def print_preview_usage() -> None:
    print(
        """用法:
  uv run scripts/calib.py preview [options]
  uv run scripts/calib.py preview cam1 [options]
  uv run scripts/calib.py preview cam2 [options]
  uv run scripts/calib.py preview stereo [options]

默认:
  preview: /dev/video0,/dev/video2
  cam1: /dev/video0
  cam2: /dev/video2
  resolution: 3840x2160 @ 30 FPS

选项:
  --device <path>
  --devices <left,right>
  --shutter <n>
  --exposure <n>
  --brightness <n>
  --auto-exposure
  --width <px>
  --height <px>
  --fps <n>
  --dry-run

窗口:
  滑条调 shutter/exposure_time_absolute 和 brightness。
  q 或 esc 退出。
"""
    )


def print_mono_usage() -> None:
    print(
        """用法:
  uv run scripts/calib.py mono cam1 [options]
  uv run scripts/calib.py mono cam2 [options]

默认:
  cam1 device: /dev/video0
  cam2 device: /dev/video2
  session: tools/calibration/captures/local/<cam>_charuco_<local_timestamp>
  output: artifacts/calibration/<cam>_<local_timestamp>

选项:
  --device <path>
  --views <n>
  --session <path>
  --output <path>
  --min-views <n>
  --max-rms-px <px>
  --capture-only
  --solve-only
  --dry-run
"""
    )


def print_stereo_usage() -> None:
    print(
        """用法:
  uv run scripts/calib.py stereo [options]

默认:
  devices: /dev/video0,/dev/video2
  session: tools/calibration/captures/local/stereo_charuco_<local_timestamp>
  left mono: latest accepted artifacts/calibration/cam1*
  right mono: latest accepted artifacts/calibration/cam2*
  output: artifacts/calibration/stereo_cam1_cam2_<local_timestamp>

选项:
  --devices <left,right>
  --left-device <path>
  --right-device <path>
  --views <n>
  --session <path>
  --left-mono <path>
  --right-mono <path>
  --output <path>
  --min-pairs <n>
  --max-rms-px <px>
  --capture-only
  --solve-only
  --dry-run
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
