#!/usr/bin/env python3

from __future__ import annotations

import sys

from process_utils import REPO_ROOT, run_streaming


YOLO_CWD = REPO_ROOT / "tools/yolo"


def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"--help", "-h"}:
        print_usage()
        return 0

    try:
        cuda = "--cuda" in argv
        argv = [item for item in argv if item != "--cuda"]
        command = argv[0]
        rest = argv[1:]
        if command == "annotate":
            return run_yolo(["annotate", *rest])
        if command == "sprites":
            return run_yolo(["sprites", *rest], extra="augment")
        if command == "augment":
            return run_yolo(["augment", *rest], extra="augment")
        if command == "benchmark":
            return run_yolo(["benchmark", *rest], extra=detect_extra(rest, cuda=cuda))
        if command == "detect-gui":
            return run_yolo(["detect-gui", *rest], extra=detect_extra(rest, cuda=cuda))
        if command == "detect-video":
            return run_yolo(["detect-video", *rest], extra=detect_extra(rest, cuda=cuda))
        raise ValueError(f"Unknown command: {command}")
    except ValueError as error:
        print(error, file=sys.stderr)
        print("", file=sys.stderr)
        print_usage()
        return 2


def run_yolo(args: list[str], *, extra: str | None = None) -> int:
    command = ["uv", "run", "--project", str(YOLO_CWD)]
    if extra is not None:
        command.extend(["--extra", extra])
    command.extend(["tennisbot-yolo", *args])
    return run_streaming(command, cwd=REPO_ROOT)


def detect_extra(args: list[str], *, cuda: bool = False) -> str | None:
    if "--dry-run" in args or "--help" in args or "-h" in args:
        return None
    return "detect-cuda" if cuda else "detect"


def print_usage() -> None:
    print(
        """用法:
  uv run scripts/yolo.py annotate [options]
  uv run scripts/yolo.py sprites extract [options]
  uv run scripts/yolo.py sprites review [options]
  uv run scripts/yolo.py augment copy-paste [options]
  uv run scripts/yolo.py benchmark tiles [options]
  uv run scripts/yolo.py detect-gui [options]
  uv run scripts/yolo.py detect-video <input-video> [options]

启动 YOLO 标注前端/后端。默认值:
  图片目录   tools/yolo/workspace/dataset/images
  标签目录   tools/yolo/workspace/dataset/labels
  排除列表   tools/yolo/workspace/dataset/excluded_images.txt
  地址       http://127.0.0.1:8765

常用命令:
  uv run scripts/yolo.py annotate
  uv run scripts/yolo.py annotate --port 8766
  uv run scripts/yolo.py annotate --images-root tools/yolo/workspace/dataset/images --labels-root tools/yolo/workspace/dataset/labels
  uv run scripts/yolo.py sprites extract
  uv run scripts/yolo.py sprites review
  uv run scripts/yolo.py augment copy-paste --config tools/yolo/configs/augmentation.toml
  uv run scripts/yolo.py benchmark tiles --dry-run
  uv run scripts/yolo.py benchmark tiles --output-markdown docs/current/yolo_tile_inference_benchmark_result_20260704.md
  uv run scripts/yolo.py detect-gui --tile
  uv run scripts/yolo.py detect-video input.mp4 --output runs/yolo-detect/input_boxes.mp4 --tile --overwrite
  uv run scripts/yolo.py detect-video input.mp4 --cuda --device 0 --tile

说明:
  annotate 使用 tools/yolo 的默认 uv 环境，不安装 torch、ultralytics 或 CUDA/NVIDIA Python 包。
  sprites 和 augment 使用 tools/yolo 的 augment extra，只安装 OpenCV/NumPy，不安装 torch、ultralytics 或 CUDA/NVIDIA Python 包。
  benchmark 实跑、纯 YOLO 相机检测 GUI 和离线视频导出默认使用 CPU-only detect extra。
  NVIDIA CUDA 推理需显式传 --cuda，并使用 tools/yolo 的 detect-cuda extra。
"""
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
