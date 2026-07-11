#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from camera_controls import (
    apply_default_camera_controls,
    build_camera_control_commands,
    display_camera_control_command,
)
from process_utils import REPO_ROOT, option_value, parse_devices, run_streaming


STEREO_CWD = REPO_ROOT / "tools/stereo"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h"}:
        print_usage()
        return 0

    try:
        command = argv[0]
        rest = argv[1:]
        if command in {"gui", "preview"}:
            return run_stereo_gui(rest)
        if command == "record":
            return run_stereo_record(rest)
        if command == "replay":
            return run_stereo_replay(rest)
        raise ValueError(f"Unknown command: {command}")
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_usage()
        return 2


def run_stereo_gui(args: list[str]) -> int:
    prepare_camera_controls(args)
    command = ["uv", "run", *detect_extra_args(args), "tennisbot-stereo", "gui", *args]
    return run_streaming(command, cwd=STEREO_CWD)


def run_stereo_record(args: list[str]) -> int:
    prepare_camera_controls(args)
    command = ["uv", "run", "tennisbot-stereo", "record", *args]
    return run_streaming(command, cwd=STEREO_CWD)


def run_stereo_replay(args: list[str]) -> int:
    replay_cwd = STEREO_CWD / "web/replay"
    if "--help" not in args and "-h" not in args:
        install_code = ensure_replay_dependencies(replay_cwd)
        if install_code != 0:
            return install_code
        build_code = run_streaming(["bun", "run", "build"], cwd=replay_cwd, stdin=subprocess.DEVNULL)
        if build_code != 0:
            return build_code
    return run_streaming(["bun", "./src/server.ts", *args], cwd=replay_cwd)


def ensure_replay_dependencies(replay_cwd: Path) -> int:
    if (replay_cwd / "node_modules/three").exists():
        return 0
    print("Installing stereo replay frontend dependencies...")
    return run_streaming(["bun", "install", "--frozen-lockfile"], cwd=replay_cwd, stdin=subprocess.DEVNULL)


def detect_extra_args(args: list[str]) -> list[str]:
    if "--dry-run" in args or "--help" in args or "-h" in args:
        return []
    return ["--extra", "detect"]


def prepare_camera_controls(args: list[str]) -> None:
    if "--help" in args or "-h" in args:
        return
    devices = camera_devices(args)
    if "--dry-run" in args:
        for command in build_camera_control_commands(devices):
            print(display_camera_control_command(command))
        sys.stdout.flush()
        return
    apply_default_camera_controls(devices, REPO_ROOT)


def camera_devices(args: list[str]) -> tuple[str, str]:
    devices = option_value(args, "--devices")
    if devices is not None:
        return parse_devices(devices)
    return (
        option_value(args, "--left-device") or "/dev/video0",
        option_value(args, "--right-device") or "/dev/video2",
    )


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/stereo.py record [options]
  uv run scripts/stereo.py preview [options]
  uv run scripts/stereo.py gui [options]
  uv run scripts/stereo.py replay [options]

录制原始左右双目视频，或启动本机 4K 双目 YOLO 坐标 GUI。默认值:
  相机       /dev/video0,/dev/video2
  采集       3840x2160@30 MJPG
  标定包     artifacts/calibration/stereo_cam1_cam2
  模型       artifacts/models/tennis_ball_yolo/model.pt

常用命令:
  uv run scripts/stereo.py record
  uv run scripts/stereo.py record --duration 60
  uv run scripts/stereo.py record --dry-run
  uv run scripts/stereo.py preview
  uv run scripts/stereo.py gui
  uv run scripts/stereo.py gui --tile
  uv run scripts/stereo.py gui --dry-run
  uv run scripts/stereo.py gui --tile --record-run
  uv run scripts/stereo.py gui --devices /dev/video0,/dev/video2
  uv run scripts/stereo.py replay

说明:
  GUI/record 启动相机前会对左右设备应用固定 V4L2 控制：手动曝光、白平衡、增益、锐度等。
  record 写入 runs/raw-stereo/<session>/left.mp4 和 right.mp4，不运行 YOLO。
  record 不传 --duration 时持续录制，预览窗口按 q 或 esc 停止。
  GUI 显示的是左相机坐标系：x right, y down, z forward。
  replay 会打开本地前端列出 runs/stereo 里的记录，时间段选择在浏览器中完成。
  YOLO 实跑会自动使用 tools/stereo 的 uv extra: detect。
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
