from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Literal

import cv2
import numpy as np

from .calibration import RuntimeStereoCalibration
from .detection import BallDetector, YoloBallDetector
from .matching import StereoBallMatcher
from .raw_recording import FrameTimestamp, RawStereoVideoRecorder
from .recording import StereoRunRecorder
from .render import render_gui, resize_to_width


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TOOL_ROOT.parents[1]
DEFAULT_CALIBRATION_PACKAGE = REPO_ROOT / "artifacts" / "calibration" / "stereo_cam1_cam2"
DEFAULT_MODEL = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo" / "model.pt"
DEFAULT_RECORD_ROOT = REPO_ROOT / "runs" / "stereo"
DEFAULT_RAW_RECORD_ROOT = REPO_ROOT / "runs" / "raw-stereo"
DEFAULT_DEVICES = ("/dev/video0", "/dev/video2")


@dataclass
class FpsMeter:
    alpha: float = 0.15
    previous: float | None = None
    fps: float = 0.0

    def update(self, timestamp: float) -> float:
        if self.previous is None:
            self.previous = timestamp
            return self.fps
        dt = max(timestamp - self.previous, 1e-6)
        self.previous = timestamp
        instant = 1.0 / dt
        self.fps = instant if self.fps <= 0.0 else (self.alpha * instant + (1.0 - self.alpha) * self.fps)
        return self.fps


def build_parser() -> argparse.ArgumentParser:
    parser_kwargs = {"formatter_class": argparse.ArgumentDefaultsHelpFormatter}
    parser = argparse.ArgumentParser(
        prog="tennisbot-stereo",
        description="TennisBot 本机 4K 双目 YOLO 坐标 GUI。",
        **parser_kwargs,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    gui = subparsers.add_parser("gui", help="打开本机双目坐标 GUI。", **parser_kwargs)
    add_gui_args(gui)
    gui.set_defaults(func=cmd_gui)
    record = subparsers.add_parser("record", help="录制原始左右双目视频。", **parser_kwargs)
    add_record_args(record)
    record.set_defaults(func=cmd_record)
    return parser


def add_gui_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--devices", help="逗号分隔的左右相机设备，会覆盖 --left-device/--right-device")
    parser.add_argument("--left-device", help="左相机设备；提供 --devices 时忽略")
    parser.add_argument("--right-device", help="右相机设备；提供 --devices 时忽略")
    parser.add_argument("--width", type=int, default=3840, help="相机采集宽度")
    parser.add_argument("--height", type=int, default=2160, help="相机采集高度")
    parser.add_argument("--fps", type=float, default=30.0, help="相机采集帧率")
    parser.add_argument("--fourcc", default="MJPG", help="相机 FOURCC")
    parser.add_argument("--calibration-package", type=Path, default=DEFAULT_CALIBRATION_PACKAGE, help="双目标定运行时包目录")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Ultralytics YOLO .pt 模型路径")
    parser.add_argument("--conf", type=float, default=0.05, help="YOLO 置信度阈值")
    parser.add_argument("--iou", type=float, default=0.5, help="NMS IoU 阈值")
    parser.add_argument("--imgsz", type=int, default=1280, help="YOLO 推理输入尺寸")
    parser.add_argument("--search-imgsz", type=int, default=1536, help="ROI tracking 未锁定时的 full-frame YOLO 输入尺寸")
    parser.add_argument("--roi-imgsz", type=int, default=960, help="ROI tracking 锁定时的 ROI YOLO 输入尺寸")
    parser.add_argument("--max-detections", type=int, default=6, help="每路每帧最大检测数")
    parser.add_argument("--device", default=None, help="Ultralytics 设备，例如 cpu、0 或 0,1")
    parser.add_argument("--class-id", type=int, default=0, help="YOLO 类别 id；-1 表示全部类别")
    parser.add_argument("--tile", action="store_true", help="对 4K 小球使用 tiled YOLO 推理")
    parser.add_argument("--tile-width", type=int, default=2048, help="tiled 推理切片宽度")
    parser.add_argument("--tile-height", type=int, default=1216, help="tiled 推理切片高度")
    parser.add_argument("--tile-overlap", type=int, default=160, help="tiled 推理切片重叠")
    parser.add_argument("--roi-tracking", action="store_true", help="启用 full-frame 搜索 + 单 ROI 跟踪")
    parser.add_argument("--roi-width", type=int, default=1024, help="锁定后 ROI 宽度")
    parser.add_argument("--roi-height", type=int, default=576, help="锁定后 ROI 高度")
    parser.add_argument("--roi-expanded-width", type=int, default=1280, help="丢帧或靠边时的扩展 ROI 宽度")
    parser.add_argument("--roi-expanded-height", type=int, default=720, help="丢帧或靠边时的扩展 ROI 高度")
    parser.add_argument("--roi-lost-after-misses", type=int, default=3, help="连续多少帧无 stereo match 后回到 full-frame 搜索")
    parser.add_argument("--roi-expand-after-misses", type=int, default=1, help="连续多少帧无 stereo match 后改用扩展 ROI")
    parser.add_argument("--roi-edge-margin-ratio", type=float, default=0.20, help="检测靠近 ROI 边缘时下一帧扩展的边缘比例")
    parser.add_argument("--roi-velocity-alpha", type=float, default=0.60, help="ROI 中心速度指数平滑系数")
    parser.add_argument("--max-epipolar-error-px", type=float, default=6.0, help="最大 rectified y 误差")
    parser.add_argument("--min-disparity-px", type=float, default=1.0, help="最小正 disparity")
    parser.add_argument("--max-disparity-px", type=float, default=1200.0, help="最大正 disparity")
    parser.add_argument("--max-depth-m", type=float, default=12.0, help="最大 z 深度")
    parser.add_argument("--display-camera-width", type=int, default=720, help="每路预览显示宽度")
    parser.add_argument("--plot-depth-m", type=float, default=10.0, help="X/Z 小图最大深度")
    parser.add_argument("--plot-x-m", type=float, default=3.0, help="X/Z 小图左右范围")
    parser.add_argument("--warmup-frames", type=int, default=5, help="相机预热帧数")
    parser.add_argument("--window", default="TennisBot Stereo Ball Position", help="OpenCV 窗口标题")
    parser.add_argument("--record-run", action="store_true", help="记录本次 GUI 运行的点流和检测流")
    parser.add_argument("--record-root", type=Path, default=DEFAULT_RECORD_ROOT, help="stereo 记录输出根目录")
    parser.add_argument("--record-preview-video", action="store_true", help="同时记录带 overlay 的预览视频")
    parser.add_argument("--dry-run", action="store_true", help="打印配置，不打开相机")


def add_record_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--devices", help="逗号分隔的左右相机设备，会覆盖 --left-device/--right-device")
    parser.add_argument("--left-device", help="左相机设备；提供 --devices 时忽略")
    parser.add_argument("--right-device", help="右相机设备；提供 --devices 时忽略")
    parser.add_argument("--width", type=int, default=3840, help="相机采集宽度")
    parser.add_argument("--height", type=int, default=2160, help="相机采集高度")
    parser.add_argument("--fps", type=float, default=30.0, help="相机采集帧率")
    parser.add_argument("--fourcc", default="MJPG", help="相机 FOURCC")
    parser.add_argument("--duration", type=float, default=0.0, help="录制秒数；0 表示直到按 q/esc 停止")
    parser.add_argument("--preview-width", type=int, default=720, help="每路预览降采样宽度")
    parser.add_argument("--warmup-frames", type=int, default=5, help="相机预热帧数")
    parser.add_argument("--window", default="TennisBot Raw Stereo Recorder", help="OpenCV 窗口标题")
    parser.add_argument("--record-root", type=Path, default=DEFAULT_RAW_RECORD_ROOT, help="原始双目视频输出根目录")
    parser.add_argument("--soft-sync-threshold-ms", type=float, default=25.0, help="软同步时间差标记阈值")
    parser.add_argument("--dry-run", action="store_true", help="打印配置，不打开相机")


def cmd_gui(args: argparse.Namespace) -> int:
    left_device, right_device = parse_devices(args)
    validate_args(args, left_device, right_device, mode="dry-run" if args.dry_run else "run")
    if args.dry_run:
        print_dry_run(args, left_device, right_device)
        return 0

    calibration = RuntimeStereoCalibration.from_package(
        args.calibration_package,
        frame_size=(args.width, args.height),
    )
    matcher = build_matcher(args, calibration)
    detector = build_detector(args)
    left_cap = open_capture(left_device, args.width, args.height, args.fps, args.fourcc)
    right_cap = open_capture(right_device, args.width, args.height, args.fps, args.fourcc)
    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    fps_meter = FpsMeter()
    recorder = create_recorder(args, left_device, right_device, calibration) if args.record_run else None
    start_perf = time.perf_counter()
    frame_id = 0

    try:
        for _ in range(max(0, args.warmup_frames)):
            left_cap.read()
            right_cap.read()

        while True:
            left_ok, left_frame = left_cap.read()
            right_ok, right_frame = right_cap.read()
            timestamp = time.perf_counter()
            timestamp_unix_ms = int(time.time() * 1000)
            if not left_ok or not right_ok:
                raise RuntimeError(f"camera read failed: left_ok={left_ok} right_ok={right_ok}")
            if left_frame.shape[:2] != right_frame.shape[:2]:
                raise RuntimeError(f"stereo frame sizes differ: left={left_frame.shape[:2]} right={right_frame.shape[:2]}")

            actual_size = (int(left_frame.shape[1]), int(left_frame.shape[0]))
            if actual_size != calibration.image_size:
                calibration = RuntimeStereoCalibration.from_package(args.calibration_package, frame_size=actual_size)
                matcher = build_matcher(args, calibration)

            left_detections, right_detections = detector.detect_pair(left_frame, right_frame)
            match = matcher.select(left_detections, right_detections)
            frame_fps = fps_meter.update(timestamp)
            canvas = render_gui(
                left_frame,
                right_frame,
                left_detections,
                right_detections,
                match,
                matcher.last_diagnostics,
                fps=frame_fps,
                frame_id=frame_id,
                display_camera_width=args.display_camera_width,
                plot_depth_m=args.plot_depth_m,
                plot_x_m=args.plot_x_m,
            )
            if recorder is not None:
                recorder.record_frame(
                    frame_id=frame_id,
                    elapsed_sec=timestamp - start_perf,
                    timestamp_unix_ms=timestamp_unix_ms,
                    left_detections=left_detections,
                    right_detections=right_detections,
                    match=match,
                    diagnostics=matcher.last_diagnostics,
                )
                recorder.record_preview(canvas, args.fps)
            cv2.imshow(args.window, canvas)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            frame_id += 1
    finally:
        if recorder is not None:
            recorder.close()
            print(f"recorded_session={recorder.session_dir}")
        left_cap.release()
        right_cap.release()
        cv2.destroyWindow(args.window)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    left_device, right_device = parse_devices(args)
    validate_record_args(args, left_device, right_device)
    if args.dry_run:
        print_record_dry_run(args, left_device, right_device)
        return 0

    left_cap = open_capture(left_device, args.width, args.height, args.fps, args.fourcc)
    right_cap = open_capture(right_device, args.width, args.height, args.fps, args.fourcc)
    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    start_perf_ns = time.perf_counter_ns()
    recorder: RawStereoVideoRecorder | None = None
    frame_id = 0

    try:
        for _ in range(max(0, args.warmup_frames)):
            left_cap.read()
            right_cap.read()

        while True:
            left_ok, left_frame = left_cap.read()
            left_timestamp = make_frame_timestamp(start_perf_ns)
            right_ok, right_frame = right_cap.read()
            right_timestamp = make_frame_timestamp(start_perf_ns)
            if not left_ok or not right_ok:
                raise RuntimeError(f"camera read failed: left_ok={left_ok} right_ok={right_ok}")
            if left_frame.shape[:2] != right_frame.shape[:2]:
                raise RuntimeError(f"stereo frame sizes differ: left={left_frame.shape[:2]} right={right_frame.shape[:2]}")

            if recorder is None:
                actual_size = (int(left_frame.shape[1]), int(left_frame.shape[0]))
                recorder = create_raw_recorder(args, left_device, right_device, actual_size)

            recorder.record_pair(
                pair_id=frame_id,
                left_frame=left_frame,
                right_frame=right_frame,
                left_timestamp=left_timestamp,
                right_timestamp=right_timestamp,
            )
            cv2.imshow(args.window, raw_preview_canvas(left_frame, right_frame, args.preview_width))
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if args.duration > 0 and left_timestamp.elapsed_sec >= args.duration:
                break
            frame_id += 1
    except KeyboardInterrupt:
        pass
    finally:
        if recorder is not None:
            recorder.close()
            print(f"recorded_session={recorder.session_dir}")
        left_cap.release()
        right_cap.release()
        cv2.destroyWindow(args.window)
    return 0


def parse_devices(args: argparse.Namespace) -> tuple[str, str]:
    if args.devices:
        devices = [item.strip() for item in str(args.devices).split(",") if item.strip()]
    else:
        devices = [item for item in (args.left_device, args.right_device) if item]
    if not devices:
        devices = list(DEFAULT_DEVICES)
    if len(devices) != 2:
        raise ValueError("stereo command requires exactly two camera devices")
    return devices[0], devices[1]


def validate_args(args: argparse.Namespace, left_device: str, right_device: str, *, mode: Literal["dry-run", "run"]) -> None:
    if not left_device or not right_device:
        raise ValueError("left and right camera devices must be non-empty")
    if len(args.fourcc) != 4:
        raise ValueError("--fourcc must contain exactly four characters, for example MJPG")
    for name in (
        "width",
        "height",
        "imgsz",
        "search_imgsz",
        "roi_imgsz",
        "display_camera_width",
        "tile_width",
        "tile_height",
        "roi_width",
        "roi_height",
        "roi_expanded_width",
        "roi_expanded_height",
    ):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    for name in ("fps", "max_epipolar_error_px", "min_disparity_px", "max_disparity_px", "max_depth_m"):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.roi_lost_after_misses <= 0:
        raise ValueError("--roi-lost-after-misses must be positive")
    if args.roi_expand_after_misses < 0:
        raise ValueError("--roi-expand-after-misses must be non-negative")
    if not 0.0 <= args.roi_edge_margin_ratio < 0.5:
        raise ValueError("--roi-edge-margin-ratio must be in [0, 0.5)")
    if not 0.0 <= args.roi_velocity_alpha <= 1.0:
        raise ValueError("--roi-velocity-alpha must be in [0, 1]")
    if args.tile_overlap < 0:
        raise ValueError("--tile-overlap must be non-negative")
    if args.tile and args.roi_tracking:
        raise ValueError("--tile and --roi-tracking cannot be used together")
    if args.max_detections <= 0:
        raise ValueError("--max-detections must be positive")
    if mode == "run" and not args.calibration_package.is_dir():
        raise FileNotFoundError(args.calibration_package)
    if mode == "run" and not args.model.is_file():
        raise FileNotFoundError(args.model)


def validate_record_args(args: argparse.Namespace, left_device: str, right_device: str) -> None:
    if not left_device or not right_device:
        raise ValueError("left and right camera devices must be non-empty")
    if len(args.fourcc) != 4:
        raise ValueError("--fourcc must contain exactly four characters, for example MJPG")
    for name in ("width", "height", "preview_width"):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    for name in ("fps", "soft_sync_threshold_ms"):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.duration < 0:
        raise ValueError("--duration must be non-negative")


def build_matcher(args: argparse.Namespace, calibration: RuntimeStereoCalibration) -> StereoBallMatcher:
    return StereoBallMatcher(
        calibration,
        max_epipolar_error_px=args.max_epipolar_error_px,
        min_disparity_px=args.min_disparity_px,
        max_disparity_px=args.max_disparity_px,
        max_depth_m=args.max_depth_m,
    )


def build_detector(args: argparse.Namespace) -> BallDetector:
    return YoloBallDetector(
        args.model,
        confidence_threshold=args.conf,
        iou_threshold=args.iou,
        imgsz=args.imgsz,
        max_detections=args.max_detections,
        device=args.device,
        class_id=None if args.class_id < 0 else args.class_id,
        tile=args.tile,
        tile_width=args.tile_width,
        tile_height=args.tile_height,
        tile_overlap=args.tile_overlap,
        roi_tracking=args.roi_tracking,
        roi_width=args.roi_width,
        roi_height=args.roi_height,
        roi_expanded_width=args.roi_expanded_width,
        roi_expanded_height=args.roi_expanded_height,
        search_imgsz=args.search_imgsz,
        roi_imgsz=args.roi_imgsz,
        roi_lost_after_misses=args.roi_lost_after_misses,
        roi_expand_after_misses=args.roi_expand_after_misses,
        roi_edge_margin_ratio=args.roi_edge_margin_ratio,
        roi_velocity_alpha=args.roi_velocity_alpha,
    )


def open_capture(device: str, width: int, height: int, fps: float, fourcc: str) -> cv2.VideoCapture:
    source: int | str = int(device) if device.isdecimal() else device
    capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not capture.isOpened():
        raise RuntimeError(f"cannot open camera device: {device}")
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    return capture


def create_recorder(
    args: argparse.Namespace,
    left_device: str,
    right_device: str,
    calibration: RuntimeStereoCalibration,
) -> StereoRunRecorder:
    return StereoRunRecorder.create(
        root=args.record_root,
        record_preview_video=args.record_preview_video,
        metadata={
            "capture": {
                "left_device": left_device,
                "right_device": right_device,
                "width": args.width,
                "height": args.height,
                "fps": args.fps,
                "fourcc": args.fourcc,
            },
            "detector": {
                "type": "yolo",
                "model": str(args.model),
                "tile": args.tile,
                "imgsz": args.imgsz,
                "roi_tracking": args.roi_tracking,
                "search_imgsz": args.search_imgsz,
                "roi_imgsz": args.roi_imgsz,
                "roi_width": args.roi_width,
                "roi_height": args.roi_height,
            },
            "calibration": {
                "package": str(args.calibration_package),
                "image_size": {
                    "width": calibration.image_size[0],
                    "height": calibration.image_size[1],
                },
                "baseline_m": calibration.baseline_m,
            },
        },
    )


def create_raw_recorder(
    args: argparse.Namespace,
    left_device: str,
    right_device: str,
    actual_size: tuple[int, int],
) -> RawStereoVideoRecorder:
    return RawStereoVideoRecorder.create(
        root=args.record_root,
        fps=args.fps,
        frame_size=actual_size,
        soft_sync_threshold_ms=args.soft_sync_threshold_ms,
        metadata={
            "capture": {
                "left_device": left_device,
                "right_device": right_device,
                "requested_width": args.width,
                "requested_height": args.height,
                "actual_width": actual_size[0],
                "actual_height": actual_size[1],
                "fps": args.fps,
                "fourcc": args.fourcc,
            },
            "recording": {
                "duration_sec": None if args.duration == 0 else args.duration,
                "preview_width": args.preview_width,
            },
        },
    )


def make_frame_timestamp(start_perf_ns: int) -> FrameTimestamp:
    now_perf_ns = time.perf_counter_ns()
    return FrameTimestamp(
        monotonic_ns=now_perf_ns,
        unix_ns=time.time_ns(),
        elapsed_sec=(now_perf_ns - start_perf_ns) / 1_000_000_000.0,
    )


def raw_preview_canvas(left_frame: np.ndarray, right_frame: np.ndarray, preview_width: int) -> np.ndarray:
    left_preview = resize_to_width(left_frame, preview_width)
    right_preview = resize_to_width(right_frame, preview_width)
    return np.hstack((left_preview, right_preview))


def print_dry_run(args: argparse.Namespace, left_device: str, right_device: str) -> None:
    print("stereo_gui=dry-run")
    print(f"devices={left_device},{right_device}")
    print(f"calibration_package={args.calibration_package}")
    print(f"model={args.model}")
    print(f"capture={args.width}x{args.height}@{args.fps:g} fourcc={args.fourcc}")
    print(
        "detector=yolo tile=%s imgsz=%s roi_tracking=%s search_imgsz=%s roi=%sx%s@%s"
        % (
            args.tile,
            args.imgsz,
            args.roi_tracking,
            args.search_imgsz,
            args.roi_width,
            args.roi_height,
            args.roi_imgsz,
        )
    )
    print(f"limits=epipolar<={args.max_epipolar_error_px:g}px depth<={args.max_depth_m:g}m")
    print(f"record_run={args.record_run} record_root={args.record_root}")


def print_record_dry_run(args: argparse.Namespace, left_device: str, right_device: str) -> None:
    duration = "unlimited" if args.duration == 0 else f"{args.duration:g}s"
    print("stereo_record=dry-run")
    print(f"devices={left_device},{right_device}")
    print(f"capture={args.width}x{args.height}@{args.fps:g} fourcc={args.fourcc}")
    print(f"duration={duration}")
    print(f"preview_width={args.preview_width}")
    print(f"record_root={args.record_root}")
    print(f"soft_sync_threshold_ms={args.soft_sync_threshold_ms:g}")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
