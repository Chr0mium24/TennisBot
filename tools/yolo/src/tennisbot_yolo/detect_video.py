from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

from .detect_gui import DEFAULT_MODEL, YoloDetector, draw_detections, put


def add_detect_video_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "detect-video",
        help="读取视频文件并导出带 YOLO 检测框的视频。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("source", type=Path, help="输入视频文件")
    parser.add_argument("--output", type=Path, default=None, help="输出视频路径；默认写到输入视频旁边")
    parser.add_argument("--overwrite", action="store_true", help="允许覆盖已有输出文件")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="YOLO .pt 模型路径")
    parser.add_argument("--conf", type=float, default=0.05, help="置信度阈值")
    parser.add_argument("--iou", type=float, default=0.5, help="NMS IoU 阈值")
    parser.add_argument("--imgsz", type=int, default=1280, help="YOLO 推理输入尺寸")
    parser.add_argument("--max-detections", type=int, default=6, help="每帧最大检测数")
    parser.add_argument("--device", default=None, help="Ultralytics 设备，例如 cpu、0 或 0,1")
    parser.add_argument("--class-id", type=int, default=0, help="要绘制的类别 id；-1 表示全部类别")
    parser.add_argument("--tile", action="store_true", help="对 4K 小球使用 tiled YOLO 推理")
    parser.add_argument("--tile-width", type=int, default=2048, help="tiled 推理切片宽度")
    parser.add_argument("--tile-height", type=int, default=1216, help="tiled 推理切片高度")
    parser.add_argument("--tile-overlap", type=int, default=160, help="切片重叠像素")
    parser.add_argument("--fourcc", default="mp4v", help="输出视频 FOURCC")
    parser.add_argument("--limit-frames", type=int, default=0, help="最多处理多少帧；0 表示全部")
    parser.add_argument("--stride", type=int, default=1, help="每隔多少帧跑一次 YOLO；跳过帧复用最近检测框")
    parser.add_argument(
        "--no-status-overlay",
        action="store_true",
        help="不绘制左上角状态信息，只保留检测框",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印解析后的配置，不打开视频或模型")
    parser.set_defaults(func=cmd_detect_video)


def cmd_detect_video(args: argparse.Namespace) -> int:
    try:
        return _cmd_detect_video(args)
    except (FileExistsError, FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _cmd_detect_video(args: argparse.Namespace) -> int:
    source = args.source.expanduser()
    model = args.model.expanduser()
    output = output_path(args.source, args.output)
    validate_args(args, output)
    if args.dry_run:
        print("detect_video=dry-run")
        print(f"source={source}")
        print(f"output={output}")
        print(f"model={model}")
        print(f"tile={args.tile} imgsz={args.imgsz} stride={args.stride}")
        print(f"fourcc={args.fourcc} overwrite={args.overwrite}")
        return 0

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "opencv-python is required for detect-video. Run with "
            "`uv run --extra detect tennisbot-yolo detect-video ...`."
        ) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open source video: {source}")

    writer: Any | None = None
    started = time.perf_counter()
    frames_written = 0
    detection_runs = 0
    total_detections = 0
    try:
        first_frame = read_frame(capture)
        if first_frame is None:
            raise RuntimeError(f"source video has no readable frames: {source}")

        height, width = first_frame.shape[:2]
        fps = capture.get(cv2.CAP_PROP_FPS)
        if fps <= 0.0:
            fps = 30.0
        writer = cv2.VideoWriter(
            str(output),
            cv2.VideoWriter_fourcc(*args.fourcc),
            fps,
            (int(width), int(height)),
        )
        if not writer.isOpened():
            raise RuntimeError(f"cannot open output video writer: {output}")

        detector = YoloDetector(
            model,
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
        )

        last_detections = []
        frame = first_frame
        frame_index = 0
        while frame is not None:
            if frame_index % args.stride == 0 or not last_detections:
                last_detections = detector.detect([frame])[0]
                detection_runs += 1
            total_detections += len(last_detections)

            annotated = frame.copy()
            draw_detections(annotated, last_detections)
            if not args.no_status_overlay:
                draw_status_overlay(
                    annotated,
                    frame_index=frame_index,
                    detections=len(last_detections),
                    model_path=model,
                    tile=args.tile,
                    imgsz=args.imgsz,
                    stride=args.stride,
                )
            writer.write(annotated)
            frames_written += 1

            if args.limit_frames > 0 and frames_written >= args.limit_frames:
                break
            frame = read_frame(capture)
            frame_index += 1
    finally:
        capture.release()
        if writer is not None:
            writer.release()

    elapsed = max(time.perf_counter() - started, 1e-6)
    print(f"output={output}")
    print(f"frames={frames_written}")
    print(f"detection_runs={detection_runs}")
    print(f"avg_detections_per_frame={total_detections / max(frames_written, 1):.3f}")
    print(f"elapsed_s={elapsed:.2f}")
    return 0


def output_path(source: Path, output: Path | None) -> Path:
    if output is not None:
        return output.expanduser()
    return source.expanduser().with_name(f"{source.stem}_yolo_boxes.mp4")


def validate_args(args: argparse.Namespace, output: Path) -> None:
    for name in ("imgsz", "max_detections", "tile_width", "tile_height", "stride"):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.limit_frames < 0:
        raise ValueError("--limit-frames must be non-negative")
    if args.tile_overlap < 0:
        raise ValueError("--tile-overlap must be non-negative")
    if len(args.fourcc) != 4:
        raise ValueError("--fourcc must contain exactly four characters, for example mp4v")
    if args.dry_run:
        return

    source = args.source.expanduser()
    if not source.is_file():
        raise FileNotFoundError(source)
    if source.stat().st_size <= 0:
        raise ValueError(f"source video is empty: {source}")
    if not args.model.expanduser().is_file():
        raise FileNotFoundError(args.model)
    if output.expanduser().resolve() == source.resolve():
        raise ValueError("output video must not overwrite the source video")
    if output.exists() and not args.overwrite:
        raise FileExistsError(f"output already exists, pass --overwrite to replace it: {output}")


def read_frame(capture: Any) -> Any | None:
    ok, frame = capture.read()
    return frame if ok else None


def draw_status_overlay(
    frame: Any,
    *,
    frame_index: int,
    detections: int,
    model_path: Path,
    tile: bool,
    imgsz: int,
    stride: int,
) -> None:
    import cv2

    width = min(frame.shape[1], 520)
    cv2.rectangle(frame, (0, 0), (width, 108), (18, 22, 26), -1)
    put(frame, "YOLO Detect Video", 16, 30, 0.78, (245, 245, 245), 2)
    put(frame, f"frame {frame_index}  detections {detections}", 16, 58, 0.55, (80, 220, 255), 2)
    put(
        frame,
        f"model {model_path.name}  {'tile' if tile else 'full'} imgsz={imgsz} stride={stride}",
        16,
        86,
        0.48,
        (180, 190, 200),
        1,
    )
