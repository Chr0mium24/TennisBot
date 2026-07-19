from __future__ import annotations

import argparse
from dataclasses import replace
import json
import math
from pathlib import Path
import subprocess
from typing import Any

import yaml
from tennisbot_camera.config import load_camera_config

from .config import ControlValue, REPO_ROOT, load_config
from .gui import run_dual_gui, run_gui
from .postprocess import ExtractOptions, NormalizeOptions, extract_yolo_frames, normalize_timestamps
from .recording import build_dual_plan, build_single_plan, record_dual, record_single


CONTROL_FLAGS = {
    "exposure": "exposure_time_absolute",
    "wb": "white_balance_temperature",
    "brightness": "brightness",
    "contrast": "contrast",
    "saturation": "saturation",
    "gamma": "gamma",
    "gain": "gain",
    "power_line_frequency": "power_line_frequency",
    "sharpness": "sharpness",
    "backlight_compensation": "backlight_compensation",
    "focus": "focus_absolute",
}


def build_parser() -> argparse.ArgumentParser:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    parser = argparse.ArgumentParser(
        prog="tennisbot-recording",
        description="TennisBot V4L2/ffmpeg camera recording CLI.",
        **parser_kwargs,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config", help="Inspect recording config.", **parser_kwargs)
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    show = config_subparsers.add_parser("show", help="Print parsed recording config.", **parser_kwargs)
    add_config_arg(show)
    show.add_argument("--json", action="store_true", help="Print JSON instead of YAML")
    show.set_defaults(func=cmd_config_show)

    record = subparsers.add_parser("record", help="Record camera video.", **parser_kwargs)
    record_subparsers = record.add_subparsers(dest="record_command", required=True)

    single = record_subparsers.add_parser("single", help="Record one V4L2 camera.", **parser_kwargs)
    add_config_arg(single)
    add_common_recording_args(single)
    add_control_override_args(single)
    single.add_argument("--device", default="", help="V4L2 device")
    single.add_argument("--camera-id", choices=("cam1", "cam2"), default="", help="Canonical camera identity")
    single.add_argument("--container", choices=("mkv", "mjpg"), default="", help="Output container")
    single.add_argument("--sample-fps", type=positive_float, default=None, help="Keep this many frames per second in MKV output")
    single.set_defaults(func=cmd_record_single)

    dual = record_subparsers.add_parser("dual", help="Record two V4L2 cameras with ffmpeg.", **parser_kwargs)
    add_config_arg(dual)
    add_common_recording_args(dual)
    add_control_override_args(dual)
    dual.add_argument("--devices", default="", help="Comma-separated camera devices")
    dual.add_argument("--preview", action="store_true", default=None, help="Open ffplay preview while recording")
    dual.add_argument("--no-preview", action="store_false", dest="preview", help="Disable ffplay preview")
    dual.add_argument("--soft-sync", action="store_true", default=None, help="Use V4L2 absolute timestamps and output offset metadata")
    dual.add_argument("--no-soft-sync", action="store_false", dest="soft_sync", help="Disable soft timestamp normalization")
    dual.add_argument("--parallel", action="store_true", default=None, help="Start one ffmpeg process per camera")
    dual.add_argument("--single-process", action="store_false", dest="parallel", help="Use one ffmpeg process for both cameras")
    dual.set_defaults(func=cmd_record_dual)

    gui = subparsers.add_parser("gui", help="Open recording GUI.", **parser_kwargs)
    gui_subparsers = gui.add_subparsers(dest="gui_command", required=True)
    gui_single = gui_subparsers.add_parser("single", help="Open one-camera preview/record GUI.", **parser_kwargs)
    add_config_arg(gui_single)
    add_control_override_args(gui_single)
    gui_single.add_argument("--device", default="", help="V4L2 device")
    gui_single.add_argument("--camera-id", choices=("cam1", "cam2"), default="", help="Canonical camera identity")
    gui_single.add_argument("--out-root", type=Path, default=None, help="Output root")
    gui_single.add_argument("--preview-width", type=positive_int, default=None, help="Preview width")
    gui_single.add_argument("--preview-fps", type=positive_float, default=None, help="Preview frames per second")
    gui_single.add_argument("--sample-fps", type=positive_float, default=None, help="Keep this many frames per second while recording")
    gui_single.add_argument("--dry-run", action="store_true", help="Print resolved GUI config without opening the camera")
    gui_single.set_defaults(func=cmd_gui_single)

    gui_dual = gui_subparsers.add_parser("dual", help="Open two-camera side-by-side preview/record GUI.", **parser_kwargs)
    add_config_arg(gui_dual)
    add_control_override_args(gui_dual)
    gui_dual.add_argument("--devices", default="", help="Comma-separated camera devices")
    gui_dual.add_argument("--out-root", type=Path, default=None, help="Output root")
    gui_dual.add_argument("--preview-width", type=positive_int, default=None, help="Per-camera preview width")
    gui_dual.add_argument("--preview-fps", type=positive_float, default=None, help="Preview frames per second")
    gui_dual.add_argument("--soft-sync", action="store_true", default=None, help="Use V4L2 absolute timestamps and output offset metadata")
    gui_dual.add_argument("--no-soft-sync", action="store_false", dest="soft_sync", help="Disable soft timestamp normalization")
    gui_dual.add_argument("--dry-run", action="store_true", help="Print resolved GUI config without opening cameras")
    gui_dual.set_defaults(func=cmd_gui_dual)

    extract = subparsers.add_parser("extract-yolo-frames", help="Extract recordings into the YOLO annotation image layout.", **parser_kwargs)
    extract.add_argument("inputs", nargs="+", help="Session names, session directories, or video files")
    extract.add_argument("--fps", type=positive_float, default=2.0, help="Frames per second to extract")
    extract.add_argument("--dataset-root", type=Path, default=Path("tools/yolo/workspace/dataset"), help="Dataset root containing images/ and labels/")
    extract.add_argument("--images-dir", type=Path, default=None, help="Output image directory")
    extract.add_argument("--labels-dir", type=Path, default=None, help="Label directory to create")
    extract.add_argument("--recordings-root", type=Path, default=Path("runs/recording"), help="Root used when an input is a session name")
    extract.add_argument("--session", default="", help="Output session prefix; valid only with one input group")
    extract.add_argument("--format", "--image-format", dest="image_format", default="jpg", help="Output image format: jpg or png")
    extract.add_argument("--jpeg-quality", type=positive_int, default=2, help="JPEG quality for ffmpeg -q:v")
    extract.add_argument("--png-compression", type=non_negative_int, default=3, help="PNG compression level")
    extract.add_argument("--cam-map", default="video0:cam1,video2:cam2", help="Comma-separated source:target camera map")
    extract.add_argument("--overwrite", action="store_true", help="Remove existing matching output frames before extracting")
    extract.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands without writing files")
    extract.set_defaults(func=cmd_extract_yolo_frames)

    normalize = subparsers.add_parser("normalize-timestamps", help="Remux videos with absolute packet timestamps to relative MKV timestamps.", **parser_kwargs)
    normalize.add_argument("inputs", nargs="+", help="Session directories or video files")
    normalize.add_argument("--output-dir", type=Path, default=None, help="Write normalized files into this directory")
    normalize.add_argument("--suffix", default="_normalized", help="Output suffix before .mkv")
    normalize.add_argument("--base-epoch", default="", help="Timestamp offset to subtract; default is earliest first video packet PTS")
    normalize.add_argument("--overwrite", action="store_true", help="Allow replacing existing output files")
    normalize.add_argument("--dry-run", action="store_true", help="Print ffmpeg commands without writing files")
    normalize.set_defaults(func=cmd_normalize_timestamps)

    return parser


def add_config_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, default=None, help="Recording YAML config")


def add_common_recording_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-root", type=Path, default=None, help="Output root")
    parser.add_argument("--duration", type=positive_float, default=None, help="Stop automatically after seconds")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without opening cameras")


def add_control_override_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--control", action="append", default=[], help="Override a V4L2 control as name=value")
    parser.add_argument("--exposure", type=number_value, default=None, help="Override exposure_time_absolute")
    parser.add_argument("--wb", "--manual-wb", type=number_value, default=None, help="Override white_balance_temperature")
    parser.add_argument("--brightness", type=number_value, default=None, help="Override brightness")
    parser.add_argument("--contrast", type=number_value, default=None, help="Override contrast")
    parser.add_argument("--saturation", type=number_value, default=None, help="Override saturation")
    parser.add_argument("--gamma", type=number_value, default=None, help="Override gamma")
    parser.add_argument("--gain", type=number_value, default=None, help="Override gain")
    parser.add_argument("--power-line-frequency", dest="power_line_frequency", type=number_value, default=None, help="Override power_line_frequency")
    parser.add_argument("--sharpness", type=number_value, default=None, help="Override sharpness")
    parser.add_argument("--backlight-compensation", dest="backlight_compensation", type=number_value, default=None, help="Override backlight_compensation")
    parser.add_argument("--focus", type=number_value, default=None, help="Override focus_absolute")


def cmd_config_show(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    payload = config_payload(config)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(payload, sort_keys=False).rstrip())
    return 0


def cmd_record_single(args: argparse.Namespace) -> int:
    config = config_with_overrides(args)
    if args.device and args.camera_id:
        raise ValueError("--device and --camera-id are mutually exclusive")
    device = load_camera_config().camera(args.camera_id).device if args.camera_id else (args.device or config.single.device)
    if args.camera_id:
        config = replace(config, single=replace(config.single, output_label=args.camera_id))
    out_root = resolve_out_root(args.out_root, config.recording.output_root)
    container = args.container or config.recording.container
    sample_fps = args.sample_fps if args.sample_fps is not None else config.recording.sample_fps
    plan = build_single_plan(
        config,
        device=device,
        out_root=out_root,
        container=container,
        duration=args.duration,
        sample_fps=sample_fps,
    )
    return record_single(plan, config, dry_run=bool(args.dry_run))


def cmd_record_dual(args: argparse.Namespace) -> int:
    config = config_with_overrides(args)
    devices = parse_devices(args.devices) if args.devices else (config.dual.devices[0], config.dual.devices[1])
    out_root = resolve_out_root(args.out_root, config.recording.output_root)
    preview = config.dual.preview if args.preview is None else bool(args.preview)
    soft_sync = config.dual.soft_sync if args.soft_sync is None else bool(args.soft_sync)
    parallel = config.dual.parallel_capture if args.parallel is None else bool(args.parallel)
    if preview and parallel:
        parallel = False
    plan = build_dual_plan(
        config,
        devices=devices,
        out_root=out_root,
        preview=preview,
        soft_sync=soft_sync,
        duration=args.duration,
    )
    return record_dual(
        plan,
        config,
        devices=devices,
        dry_run=bool(args.dry_run),
        preview=preview,
        parallel_capture=parallel,
    )


def cmd_gui_single(args: argparse.Namespace) -> int:
    config = config_with_overrides(args)
    if args.device and args.camera_id:
        raise ValueError("--device and --camera-id are mutually exclusive")
    device = load_camera_config().camera(args.camera_id).device if args.camera_id else (args.device or config.single.device)
    if args.camera_id:
        config = replace(config, single=replace(config.single, output_label=args.camera_id))
    out_root = resolve_out_root(args.out_root, config.recording.output_root)
    preview_width = args.preview_width if args.preview_width is not None else config.preview.width
    preview_fps = args.preview_fps if args.preview_fps is not None else config.preview.fps
    sample_fps = args.sample_fps if args.sample_fps is not None else config.recording.sample_fps
    if args.dry_run:
        print("recording_gui=dry-run")
        print(f"device={device}")
        print(f"out_root={out_root}")
        print(f"capture={config.capture.video_size}@{config.capture.fps:g} input_format={config.capture.input_format}")
        print(f"preview={preview_width}px@{preview_fps:g}fps")
        print(f"sample_fps={'' if sample_fps is None else sample_fps:g}")
        print(f"controls={config.v4l2_controls_string()}")
        return 0
    run_gui(
        config=config,
        device=device,
        out_root=out_root,
        preview_width=preview_width,
        preview_fps=preview_fps,
        sample_fps=sample_fps,
    )
    return 0


def cmd_gui_dual(args: argparse.Namespace) -> int:
    config = config_with_overrides(args)
    devices = parse_devices(args.devices) if args.devices else (config.dual.devices[0], config.dual.devices[1])
    out_root = resolve_out_root(args.out_root, config.recording.output_root)
    preview_width = args.preview_width if args.preview_width is not None else config.preview.width
    preview_fps = args.preview_fps if args.preview_fps is not None else config.preview.fps
    soft_sync = config.dual.soft_sync if args.soft_sync is None else bool(args.soft_sync)
    if args.dry_run:
        print("recording_dual_gui=dry-run")
        print(f"devices={devices[0]},{devices[1]}")
        print(f"out_root={out_root}")
        print(f"capture={config.capture.video_size}@{config.capture.fps:g} input_format={config.capture.input_format}")
        print(f"preview={preview_width}px@{preview_fps:g}fps per_camera")
        print(f"soft_sync={soft_sync}")
        print(f"controls={config.v4l2_controls_string()}")
        return 0
    run_dual_gui(
        config=config,
        devices=devices,
        out_root=out_root,
        preview_width=preview_width,
        preview_fps=preview_fps,
        soft_sync=soft_sync,
    )
    return 0


def cmd_extract_yolo_frames(args: argparse.Namespace) -> int:
    return extract_yolo_frames(
        ExtractOptions(
            inputs=list(args.inputs),
            fps=float(args.fps),
            dataset_root=args.dataset_root,
            images_dir=args.images_dir,
            labels_dir=args.labels_dir,
            recordings_root=args.recordings_root,
            session=str(args.session),
            image_format=str(args.image_format),
            jpeg_quality=int(args.jpeg_quality),
            png_compression=int(args.png_compression),
            cam_map=str(args.cam_map),
            overwrite=bool(args.overwrite),
            dry_run=bool(args.dry_run),
        )
    )


def cmd_normalize_timestamps(args: argparse.Namespace) -> int:
    if args.base_epoch:
        try:
            float(args.base_epoch)
        except ValueError as error:
            raise ValueError("--base-epoch must be a number") from error
    return normalize_timestamps(
        NormalizeOptions(
            inputs=list(args.inputs),
            output_dir=args.output_dir,
            suffix=str(args.suffix),
            base_epoch=str(args.base_epoch),
            overwrite=bool(args.overwrite),
            dry_run=bool(args.dry_run),
        )
    )


def config_with_overrides(args: argparse.Namespace):
    config = load_config(args.config)
    return config.with_control_overrides(control_overrides(args))


def control_overrides(args: argparse.Namespace) -> dict[str, ControlValue]:
    overrides: dict[str, ControlValue] = {}
    for flag, control_name in CONTROL_FLAGS.items():
        value = getattr(args, flag, None)
        if value is not None:
            overrides[control_name] = value
    for item in getattr(args, "control", []):
        if "=" not in item:
            raise ValueError("--control must use name=value")
        name, value = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("--control name cannot be empty")
        overrides[name] = parse_control_value(value)
    return overrides


def parse_devices(value: str) -> tuple[str, str]:
    devices = [device.strip() for device in value.split(",") if device.strip()]
    if len(devices) != 2:
        raise ValueError("--devices requires exactly two comma-separated devices")
    return devices[0], devices[1]


def resolve_out_root(value: Path | None, default: Path) -> Path:
    if value is None:
        return default
    if value.is_absolute():
        return value.expanduser()
    text = str(value)
    if text.startswith("~"):
        return Path(text).expanduser()
    return REPO_ROOT / value


def config_payload(config) -> dict[str, Any]:
    return {
        "schema_version": config.schema_version,
        "path": str(config.path),
        "capture": {
            "width": config.capture.width,
            "height": config.capture.height,
            "fps": config.capture.fps,
            "input_format": config.capture.input_format,
            "pixel_format": config.capture.pixel_format,
            "settle_seconds": config.capture.settle_seconds,
        },
        "recording": {
            "output_root": str(config.recording.output_root),
            "container": config.recording.container,
            "sample_fps": config.recording.sample_fps,
            "thread_queue_size": config.recording.thread_queue_size,
        },
        "single": {
            "device": config.single.device,
            "output_label": config.single.output_label,
        },
        "dual": {
            "devices": list(config.dual.devices),
            "preview": config.dual.preview,
            "soft_sync": config.dual.soft_sync,
            "parallel_capture": config.dual.parallel_capture,
        },
        "preview": {
            "width": config.preview.width,
            "fps": config.preview.fps,
            "port": config.preview.port,
        },
        "controls": config.controls,
    }


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive integer") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a non-negative integer") from error
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be a non-negative integer")
    return parsed


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a positive number") from error
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return parsed


def number_value(value: str) -> int | float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a number") from error
    if not math.isfinite(parsed):
        raise argparse.ArgumentTypeError("must be a finite number")
    if parsed.is_integer():
        return int(parsed)
    return parsed


def parse_control_value(value: str) -> ControlValue:
    if value == "null":
        return None
    try:
        return number_value(value)
    except argparse.ArgumentTypeError:
        return value


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
