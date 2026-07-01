from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from camera_calib_lab.brightness import BrightnessOptions, print_brightness_report, run_camera_brightness_check
from camera_calib_lab.camera_preview import PreviewOptions, run_camera_preview
from camera_calib_lab.cli_summary import capture_summary, mono_solve_summary, stereo_solve_summary
from camera_calib_lab.capture_gui import run_mono_charuco_gui, run_stereo_charuco_gui
from camera_calib_lab.solve import solve_mono_package, solve_stereo_package


def capture_charuco_auto_gui(args: argparse.Namespace) -> int:
    manifest = run_mono_charuco_gui(
        config_path=Path(args.config),
        output_path=Path(args.output),
        calibration_output=Path(args.calibration_output) if args.calibration_output else None,
        views=int(args.views),
        device=args.device,
        camera_id=args.camera_id or None,
    )
    print(capture_summary(manifest))
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
    print(capture_summary(manifest))
    return 0 if manifest["status"] in {"ready", "partial"} else 1


def solve_mono(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    package = solve_mono_package(
        session_path=Path(args.session) if args.session else None,
        observations_path=Path(args.observations) if args.observations else None,
        output_path=output_path,
        config_path=Path(args.config),
        camera_id=args.camera_id or None,
        min_views=int(args.min_views),
        max_rms_px=float(args.max_rms_px),
    )
    verification = read_written_json(output_path / "verification.json")
    print(mono_solve_summary(package, verification, output_path))
    return 0 if package["accepted"] else 1


def solve_stereo(args: argparse.Namespace) -> int:
    output_path = Path(args.output)
    package = solve_stereo_package(
        session_path=Path(args.session) if args.session else None,
        observations_path=Path(args.observations) if args.observations else None,
        left_mono_path=Path(args.left_mono),
        right_mono_path=Path(args.right_mono),
        output_path=output_path,
        config_path=Path(args.config),
        left_camera_id=args.left_camera_id,
        right_camera_id=args.right_camera_id,
        min_pairs=int(args.min_pairs),
        max_rms_px=float(args.max_rms_px),
        epipolar_warning_px=float(args.epipolar_warning_px),
        rectification_warning_px=float(args.rectification_warning_px),
    )
    print(stereo_solve_summary(package, output_path))
    return 0 if package["accepted"] else 1


def read_written_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def camera_brightness(args: argparse.Namespace) -> int:
    devices = None if args.devices == "" else [device.strip() for device in args.devices.split(",") if device.strip()]
    report, exit_code = run_camera_brightness_check(
        BrightnessOptions(
            devices=devices,
            width=int(args.width),
            height=int(args.height),
            fps=int(args.fps),
            input_format=args.input_format,
            timeout_ms=int(args.timeout_ms),
            json_output=bool(args.json),
            dry_run=bool(args.dry_run),
        )
    )
    print_brightness_report(report, json_output=bool(args.json))
    return exit_code


def camera_preview(args: argparse.Namespace) -> int:
    try:
        devices = parse_preview_devices(args)
    except ValueError as error:
        print(str(error))
        return 2
    report = run_camera_preview(
        PreviewOptions(
            devices=devices,
            width=int(args.width),
            height=int(args.height),
            fps=float(args.fps),
            fourcc=str(args.fourcc),
            exposure=None if args.exposure is None else int(args.exposure),
            brightness=None if args.brightness is None else int(args.brightness),
            auto_exposure=bool(args.auto_exposure),
            dry_run=bool(args.dry_run),
            max_width=int(args.max_width),
        )
    )
    if args.dry_run:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def parse_preview_devices(args: argparse.Namespace) -> list[str]:
    if args.device and args.devices:
        raise ValueError("camera preview accepts either --device or --devices, not both")
    if args.device:
        return [str(args.device)]
    devices = str(args.devices) or "/dev/video0,/dev/video2"
    parsed = [device.strip() for device in devices.split(",") if device.strip()]
    if not parsed or len(parsed) > 2:
        raise ValueError("camera preview requires one or two devices")
    return parsed


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
    mono.add_argument("--camera-id", default="", help="写入采集会话的相机 ID；默认使用配置文件")
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

    camera = subparsers.add_parser("camera", help="检查本机相机设备。", **parser_kwargs)
    camera_subparsers = camera.add_subparsers(dest="camera_command", required=True)

    brightness = camera_subparsers.add_parser("brightness", help="采集一帧并估算 USB 相机平均亮度。", **parser_kwargs)
    brightness.add_argument("--devices", default="", help="逗号分隔的相机设备；默认自动选择前两个 USB V4L2 采集设备")
    brightness.add_argument("--width", type=int, default=1280, help="采集宽度")
    brightness.add_argument("--height", type=int, default=720, help="采集高度")
    brightness.add_argument("--fps", type=int, default=30, help="采集帧率")
    brightness.add_argument("--input-format", default="mjpeg", help="V4L2 输入格式；失败后会自动重试默认格式")
    brightness.add_argument("--timeout-ms", type=int, default=5000, help="单设备采集超时")
    brightness.add_argument("--json", action="store_true", help="输出 JSON 报告")
    brightness.add_argument("--dry-run", action="store_true", help="只解析设备，不调用 ffmpeg 采集")
    brightness.set_defaults(handler=camera_brightness)

    preview = camera_subparsers.add_parser("preview", help="打开相机实时画面并调节快门/亮度。", **parser_kwargs)
    preview.add_argument("--device", default="", help="单相机设备；与 --devices 二选一")
    preview.add_argument("--devices", default="", help="逗号分隔的一到两个相机设备；默认 /dev/video0,/dev/video2")
    preview.add_argument("--width", type=int, default=3840, help="预览采集宽度")
    preview.add_argument("--height", type=int, default=2160, help="预览采集高度")
    preview.add_argument("--fps", type=float, default=30.0, help="预览采集帧率")
    preview.add_argument("--fourcc", default="MJPG", help="OpenCV FourCC")
    preview.add_argument("--shutter", "--exposure", dest="exposure", type=int, default=None, help="初始 exposure_time_absolute")
    preview.add_argument("--brightness", type=int, default=None, help="初始 brightness")
    preview.add_argument("--auto-exposure", action="store_true", help="保留自动曝光；默认切到手动曝光以允许调快门")
    preview.add_argument("--max-width", type=int, default=760, help="单路画面的最大预览宽度")
    preview.add_argument("--dry-run", action="store_true", help="只打印设备和控制项，不打开视频窗口")
    preview.set_defaults(handler=camera_preview)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
