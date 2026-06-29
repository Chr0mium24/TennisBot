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
    parser = argparse.ArgumentParser(
        prog="camera-calib-lab",
        description="TennisBot fixed DFOptix ChArUco OpenCV calibration GUI.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    capture = subparsers.add_parser("capture", help="Capture local ChArUco calibration sessions.")
    capture_subparsers = capture.add_subparsers(dest="capture_command", required=True)

    mono = capture_subparsers.add_parser("charuco-auto-gui", help="Run the mono ChArUco auto-capture GUI.")
    mono.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml")
    mono.add_argument("--output", default="captures/local/dfoptix_charuco_auto_session")
    mono.add_argument("--calibration-output", default="")
    mono.add_argument("--views", type=int, default=30)
    mono.add_argument("--device", default="/dev/video0")
    mono.set_defaults(handler=capture_charuco_auto_gui)

    stereo = capture_subparsers.add_parser("stereo-charuco-auto-gui", help="Run the stereo ChArUco auto-capture GUI.")
    stereo.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml")
    stereo.add_argument("--output", default="captures/local/dfoptix_stereo_charuco_auto_session")
    stereo.add_argument("--calibration-output", default="")
    stereo.add_argument("--views", type=int, default=30)
    stereo.add_argument("--left-device", default="/dev/video0")
    stereo.add_argument("--right-device", default="/dev/video2")
    stereo.set_defaults(handler=capture_stereo_charuco_auto_gui)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
