#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


def usage() -> None:
    print(
        """用法:
  uv run scripts/record.py mono cam1 [--gui] [options]
  uv run scripts/record.py mono cam2 [--gui] [options]
  uv run scripts/record.py stereo [--gui] [options]

默认无 GUI，适合 SSH。--gui 使用相同 ffmpeg 录制核心并增加预览和开始/停止控件。
record 只负责原始视频录制；数据集抽帧、时间戳修复、YOLO 和三角化不属于此入口。
"""
    )


def normalize(argv: list[str]) -> list[str]:
    if not argv or argv[0] in {"-h", "--help"}:
        usage()
        raise SystemExit(0)
    mode = argv[0]
    rest = argv[1:]
    gui = "--gui" in rest
    rest = [item for item in rest if item != "--gui"]
    if mode == "mono":
        if not rest or rest[0] not in {"cam1", "cam2"}:
            raise ValueError("mono requires cam1 or cam2")
        camera_id, rest = rest[0], rest[1:]
        return (["gui", "single"] if gui else ["record", "single"]) + ["--camera-id", camera_id, *rest]
    if mode == "stereo":
        return (["gui", "dual"] if gui else ["record", "dual"]) + rest
    raise ValueError(f"unknown recording mode: {mode}")


def main(argv: list[str]) -> int:
    try:
        command = normalize(argv)
    except ValueError as error:
        print(error, file=sys.stderr)
        usage()
        return 2
    return run_streaming(
        ["uv", "run", "--project", str(REPO_ROOT / "tools/recording"), "tennisbot-recording", *command]
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
