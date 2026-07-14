#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


RECORDING_CWD = REPO_ROOT / "tools/recording"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h"}:
        print_usage()
        return 0
    command = normalize_args(argv)
    return run_streaming(["uv", "run", "tennisbot-recording", *command], cwd=RECORDING_CWD)


def normalize_args(argv: list[str]) -> list[str]:
    command = argv[0]
    rest = argv[1:]
    if command in {"single", "mono"}:
        return ["record", "single", *rest]
    if command in {"dual", "stereo"}:
        return ["record", "dual", *rest]
    if command == "gui":
        if rest and rest[0] == "single":
            return ["gui", *rest]
        return ["gui", "single", *rest]
    if command == "extract":
        return ["extract-yolo-frames", *rest]
    if command == "normalize":
        return ["normalize-timestamps", *rest]
    return argv


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/recording.py single [options]
  uv run scripts/recording.py dual [options]
  uv run scripts/recording.py gui [options]
  uv run scripts/recording.py extract [options] <session|dir|video...>
  uv run scripts/recording.py normalize [options] <dir|video...>
  uv run scripts/recording.py config show

默认配置:
  tools/recording/configs/tennis_camera_recording.yaml

常用命令:
  uv run scripts/recording.py single --dry-run
  uv run scripts/recording.py single --duration 60
  uv run scripts/recording.py single --duration 60 --sample-fps 3
  uv run scripts/recording.py dual --dry-run
  uv run scripts/recording.py dual --duration 60
  uv run scripts/recording.py dual --preview
  uv run scripts/recording.py gui
  uv run scripts/recording.py extract --dry-run 20260701_205507
  uv run scripts/recording.py normalize --dry-run --base-epoch 1782893181 runs/recording/<session>

说明:
  single/dual 启动前会从 YAML 配置加载 V4L2 控制，包括 exposure_time_absolute、白平衡、亮度、增益和锐度等。
  默认输出目录是 runs/recording，已被仓库忽略。
  dual 的软同步沿用 V4L2 absolute timestamps + output_ts_offset；这是软件时间戳归一化，不是硬件同步。
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
