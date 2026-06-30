from __future__ import annotations

import argparse
import json
from pathlib import Path

from camera_calib_lab.capture_gui import run_mono_charuco_gui, run_stereo_charuco_gui
from camera_calib_lab.solve import solve_mono_package, solve_stereo_package


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


def solve_mono(args: argparse.Namespace) -> int:
    package = solve_mono_package(
        session_path=Path(args.session) if args.session else None,
        observations_path=Path(args.observations) if args.observations else None,
        output_path=Path(args.output),
        config_path=Path(args.config),
        camera_id=args.camera_id or None,
        min_views=int(args.min_views),
        max_rms_px=float(args.max_rms_px),
    )
    print(json.dumps(package, indent=2, sort_keys=True))
    return 0 if package["accepted"] else 1


def solve_stereo(args: argparse.Namespace) -> int:
    package = solve_stereo_package(
        session_path=Path(args.session) if args.session else None,
        observations_path=Path(args.observations) if args.observations else None,
        left_mono_path=Path(args.left_mono),
        right_mono_path=Path(args.right_mono),
        output_path=Path(args.output),
        config_path=Path(args.config),
        left_camera_id=args.left_camera_id,
        right_camera_id=args.right_camera_id,
        min_pairs=int(args.min_pairs),
        max_rms_px=float(args.max_rms_px),
        epipolar_warning_px=float(args.epipolar_warning_px),
        rectification_warning_px=float(args.rectification_warning_px),
    )
    print(json.dumps(package, indent=2, sort_keys=True))
    return 0 if package["accepted"] else 1


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

    solve = subparsers.add_parser("solve", help="求解 ChArUco 标定并导出运行时包。", **parser_kwargs)
    solve_subparsers = solve.add_subparsers(dest="solve_command", required=True)

    mono_solve = solve_subparsers.add_parser("mono", help="从单目采集会话求解内参。", **parser_kwargs)
    mono_solve.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml", help="采集/目标配置文件")
    mono_solve.add_argument("--session", default="", help="单目采集会话目录；与 --observations 二选一")
    mono_solve.add_argument("--observations", default="", help="已检测的 observations.json；与 --session 二选一")
    mono_solve.add_argument("--output", required=True, help="单目标定包输出目录")
    mono_solve.add_argument("--camera-id", default="", help="输出相机 ID；默认使用会话中的相机 ID")
    mono_solve.add_argument("--min-views", type=int, default=8, help="接受标定所需最少有效视角")
    mono_solve.add_argument("--max-rms-px", type=float, default=1.0, help="接受标定的最大重投影 RMS")
    mono_solve.set_defaults(handler=solve_mono)

    stereo_solve = solve_subparsers.add_parser("stereo", help="从双目采集会话和单目包求解双目外参。", **parser_kwargs)
    stereo_solve.add_argument("--config", default="configs/dfoptix_charuco_15mm_capture.yaml", help="采集/目标配置文件")
    stereo_solve.add_argument("--session", default="", help="双目采集会话目录；与 --observations 二选一")
    stereo_solve.add_argument("--observations", default="", help="已检测的 observations.json；与 --session 二选一")
    stereo_solve.add_argument("--left-mono", required=True, help="左相机单目标定包目录")
    stereo_solve.add_argument("--right-mono", required=True, help="右相机单目标定包目录")
    stereo_solve.add_argument("--output", required=True, help="双目标定包输出目录")
    stereo_solve.add_argument("--left-camera-id", default="cam1", help="输出左相机 ID")
    stereo_solve.add_argument("--right-camera-id", default="cam2", help="输出右相机 ID")
    stereo_solve.add_argument("--min-pairs", type=int, default=12, help="接受标定所需最少有效双目组")
    stereo_solve.add_argument("--max-rms-px", type=float, default=2.0, help="接受标定的最大 stereo RMS")
    stereo_solve.add_argument("--epipolar-warning-px", type=float, default=2.0, help="epipolar RMS 质量警告阈值")
    stereo_solve.add_argument("--rectification-warning-px", type=float, default=2.0, help="校正后 y 误差 p95 质量警告阈值")
    stereo_solve.set_defaults(handler=solve_stereo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
