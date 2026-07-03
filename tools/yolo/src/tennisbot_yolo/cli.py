from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .augmentation import add_augment_parser
from .detect_gui import add_detect_gui_parser
from .package import PackageVerificationError, create_model_package, verify_model_package
from .sprites import add_sprites_parser


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TOOL_ROOT.parents[1]
DEFAULT_IMAGES_ROOT = TOOL_ROOT / "yolo" / "dataset" / "images"
DEFAULT_LABELS_ROOT = TOOL_ROOT / "yolo" / "dataset" / "labels"
DEFAULT_EXCLUDED_FILE = TOOL_ROOT / "yolo" / "dataset" / "excluded_images.txt"
DEFAULT_MODEL_PACKAGE = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo"
ANNOTATOR_SCRIPT = TOOL_ROOT / "yolo" / "scripts" / "serve_annotator.py"


def cmd_annotate(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(ANNOTATOR_SCRIPT),
        "--images",
        str(args.images_root),
        "--labels",
        str(args.labels_root),
        "--excluded",
        str(args.excluded_file),
        "--host",
        args.host,
        "--port",
        str(args.port),
    ]
    return subprocess.call(command, cwd=TOOL_ROOT)


def cmd_package_create(args: argparse.Namespace) -> int:
    try:
        output = create_model_package(
            args.output_dir,
            default_model=args.default_model,
            model_pt=args.model_pt,
            model_onnx=args.model_onnx,
            model_rknn=args.model_rknn,
            eval_report=args.eval_report,
            eval_metrics=args.eval_metrics,
            dry_run=args.dry_run,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"package={output}")
    return 0


def cmd_package_verify(args: argparse.Namespace) -> int:
    try:
        verify_model_package(args.path)
    except PackageVerificationError as exc:
        for error in exc.errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"verified={args.path.resolve()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    parser = argparse.ArgumentParser(
        prog="tennisbot-yolo",
        description="TennisBot YOLO 标注、检测和运行时模型包工具。",
        **parser_kwargs,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    annotate = subparsers.add_parser("annotate", help="启动本机 YOLO 标注前端/后端。", **parser_kwargs)
    annotate.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT, help="图片根目录")
    annotate.add_argument("--labels-root", type=Path, default=DEFAULT_LABELS_ROOT, help="YOLO 标签根目录")
    annotate.add_argument("--excluded-file", type=Path, default=DEFAULT_EXCLUDED_FILE, help="排除图片列表")
    annotate.add_argument("--host", default="127.0.0.1", help="HTTP 监听地址")
    annotate.add_argument("--port", type=int, default=8765, help="HTTP 监听端口")
    annotate.set_defaults(func=cmd_annotate)

    add_detect_gui_parser(subparsers)
    add_sprites_parser(subparsers)
    add_augment_parser(subparsers)

    package = subparsers.add_parser("package", help="创建和验证运行时模型包。", **parser_kwargs)
    package_subparsers = package.add_subparsers(dest="package_command", required=True)

    create = package_subparsers.add_parser("create", help="创建 YOLO 运行时模型包。", **parser_kwargs)
    create.add_argument("--output-dir", type=Path, default=DEFAULT_MODEL_PACKAGE, help="运行时模型包输出目录")
    create.add_argument("--model-pt", type=Path, help="源 PyTorch .pt 模型")
    create.add_argument("--model-onnx", type=Path, help="源 ONNX 模型")
    create.add_argument("--model-rknn", type=Path, help="源 RKNN 模型")
    create.add_argument("--eval-report", type=Path, help="源评估 Markdown 报告")
    create.add_argument("--eval-metrics", type=Path, help="源评估指标 JSON")
    create.add_argument("--default-model", choices=("pt", "onnx", "rknn"), default="onnx", help="默认使用的模型类型")
    create.add_argument("--dry-run", action="store_true", help="创建不可推理的占位模型包")
    create.set_defaults(func=cmd_package_create)

    verify = package_subparsers.add_parser("verify", help="验证 YOLO 运行时模型包。", **parser_kwargs)
    verify.add_argument("--path", type=Path, default=DEFAULT_MODEL_PACKAGE, help="运行时模型包目录")
    verify.set_defaults(func=cmd_package_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
