from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .package import PackageVerificationError, create_model_package, verify_model_package


def cmd_package_create(args: argparse.Namespace) -> int:
    try:
        output = create_model_package(
            args.output_dir,
            default_model=args.default_model,
            model_pt=args.model_pt,
            model_onnx=args.model_onnx,
            model_rknn=args.model_rknn,
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

    package = subparsers.add_parser("package", help="Create and verify runtime model packages.")
    package_subparsers = package.add_subparsers(dest="package_command", required=True)

    create = package_subparsers.add_parser("create", help="Create a YOLO runtime model package.")
    create.add_argument("--output-dir", type=Path, required=True)
    create.add_argument("--model-pt", type=Path)
    create.add_argument("--model-onnx", type=Path)
    create.add_argument("--model-rknn", type=Path)
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
