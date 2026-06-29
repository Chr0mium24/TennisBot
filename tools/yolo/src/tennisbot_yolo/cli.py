from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .package import PackageVerificationError, create_model_package, verify_model_package


TOOL_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGES_ROOT = TOOL_ROOT / "yolo" / "dataset" / "images"
DEFAULT_LABELS_ROOT = TOOL_ROOT / "yolo" / "dataset" / "labels"
DEFAULT_EXCLUDED_FILE = TOOL_ROOT / "yolo" / "dataset" / "excluded_images.txt"
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
    parser = argparse.ArgumentParser(
        prog="tennisbot-yolo",
        description="TennisBot YOLO runtime package tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    annotate = subparsers.add_parser("annotate", help="Serve the local YOLO annotation frontend/backend.")
    annotate.add_argument("--images-root", type=Path, default=DEFAULT_IMAGES_ROOT)
    annotate.add_argument("--labels-root", type=Path, default=DEFAULT_LABELS_ROOT)
    annotate.add_argument("--excluded-file", type=Path, default=DEFAULT_EXCLUDED_FILE)
    annotate.add_argument("--host", default="127.0.0.1")
    annotate.add_argument("--port", type=int, default=8765)
    annotate.set_defaults(func=cmd_annotate)

    package = subparsers.add_parser("package", help="Create and verify runtime model packages.")
    package_subparsers = package.add_subparsers(dest="package_command", required=True)

    create = package_subparsers.add_parser("create", help="Create a YOLO runtime model package.")
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--model-pt", type=Path)
    create.add_argument("--model-onnx", type=Path)
    create.add_argument("--model-rknn", type=Path)
    create.add_argument("--eval-report", type=Path)
    create.add_argument("--eval-metrics", type=Path)
    create.add_argument("--default-model", choices=("pt", "onnx", "rknn"), default="onnx")
    create.add_argument("--dry-run", action="store_true")
    create.set_defaults(func=cmd_package_create)

    verify = package_subparsers.add_parser("verify", help="Verify a YOLO runtime model package.")
    verify.add_argument("--path", type=Path, required=True)
    verify.set_defaults(func=cmd_package_verify)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
