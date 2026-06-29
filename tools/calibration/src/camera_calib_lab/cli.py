from __future__ import annotations

import argparse
import json
from pathlib import Path

from camera_calib_lab.capture_gui import run_mono_charuco_gui, run_stereo_charuco_gui


def capture_charuco_auto_gui(args: argparse.Namespace) -> int:
    manifest = run_mono_charuco_gui(
        config_path=Path(args.config),
        output_path=Path(args.output),
        calibration_output=Path(args.calibration_output) if args.calibration_output else None,
        views=int(args.views),
        device=args.device,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] in {"ready", "partial"} else 1


def capture_stereo_charuco_auto_gui(args: argparse.Namespace) -> int:
    manifest = run_stereo_charuco_gui(
        config_path=Path(args.config),
        output_path=Path(args.output),
        calibration_output=Path(args.calibration_output) if args.calibration_output else None,
        views=int(args.views),
        left_device=args.left_device,
        right_device=args.right_device,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["status"] in {"ready", "partial"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    parser = argparse.ArgumentParser(
        prog="camera-calib-lab",
        description="TennisBot 固定 DFOptix ChArUco OpenCV 标定采集 GUI。",
        **parser_kwargs,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="采集本机 ChArUco 标定会话。", **parser_kwargs)
    capture_subparsers = capture.add_subparsers(dest="capture_command", required=True)

    mono = capture_subparsers.add_parser("charuco-auto-gui", help="运行单目 ChArUco 自动采集 GUI。", **parser_kwargs)
    mono.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml", help="采集配置文件")
    mono.add_argument("--output", default="captures/local/dfoptix_charuco_auto_session", help="采集会话输出目录")
    mono.add_argument("--calibration-output", default="", help="预留的标定输出路径")
    mono.add_argument("--views", type=int, default=30, help="目标有效采集张数")
    mono.add_argument("--device", default="/dev/video0", help="单目相机设备")
    mono.set_defaults(handler=capture_charuco_auto_gui)

    stereo = capture_subparsers.add_parser(
        "stereo-charuco-auto-gui",
        help="运行双目 ChArUco 自动采集 GUI。",
        **parser_kwargs,
    )
    stereo.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml", help="采集配置文件")
    stereo.add_argument("--output", default="captures/local/dfoptix_stereo_charuco_auto_session", help="采集会话输出目录")
    stereo.add_argument("--calibration-output", default="", help="预留的标定输出路径")
    stereo.add_argument("--views", type=int, default=30, help="目标有效双目组数")
    stereo.add_argument("--left-device", default="/dev/video0", help="左相机设备")
    stereo.add_argument("--right-device", default="/dev/video2", help="右相机设备")
    stereo.set_defaults(handler=capture_stereo_charuco_auto_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
