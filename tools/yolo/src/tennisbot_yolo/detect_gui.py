from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


TOOL_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = TOOL_ROOT.parents[1]
DEFAULT_MODEL = REPO_ROOT / "artifacts" / "models" / "tennis_ball_yolo" / "model.pt"
DEFAULT_DEVICES = ("/dev/video0", "/dev/video2")


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int

    @property
    def x(self) -> float:
        return 0.5 * (self.x1 + self.x2)

    @property
    def y(self) -> float:
        return 0.5 * (self.y1 + self.y2)

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


class YoloDetector:
    def __init__(
        self,
        model_path: Path,
        *,
        confidence_threshold: float,
        iou_threshold: float,
        imgsz: int,
        max_detections: int,
        device: str | None,
        class_id: int | None,
        tile: bool,
        tile_width: int,
        tile_height: int,
        tile_overlap: int,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "ultralytics is required for detect-gui. Run with "
                "`uv run --extra detect tennisbot-yolo detect-gui ...`."
            ) from exc

        self.model = YOLO(str(model_path))
        self.confidence_threshold = confidence_threshold
        self.iou_threshold = iou_threshold
        self.imgsz = imgsz
        self.max_detections = max_detections
        self.device = device
        self.class_id = class_id
        self.tile = tile
        self.tile_width = tile_width
        self.tile_height = tile_height
        self.tile_overlap = tile_overlap

    def detect(self, frames: list[Any]) -> list[list[Detection]]:
        if self.tile:
            return [self._detect_tiled(frame) for frame in frames]

        results = self.model.predict(
            source=frames,
            imgsz=self.imgsz,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=self.max_detections,
            device=self.device,
            stream=False,
            verbose=False,
        )
        return [_detections_from_result(result, 0, 0, self.class_id) for result in results]

    def _detect_tiled(self, frame: Any) -> list[Detection]:
        tiles = list(make_tiles(frame, self.tile_width, self.tile_height, self.tile_overlap))
        results = self.model.predict(
            source=[tile for tile, _, _ in tiles],
            imgsz=self.imgsz,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=self.max_detections,
            device=self.device,
            stream=False,
            verbose=False,
        )
        detections: list[Detection] = []
        for result, (_, offset_x, offset_y) in zip(results, tiles, strict=True):
            detections.extend(_detections_from_result(result, offset_x, offset_y, self.class_id))
        return nms_detections(detections, self.iou_threshold)[: self.max_detections]


class FpsMeter:
    def __init__(self, alpha: float = 0.15) -> None:
        self.alpha = alpha
        self.previous: float | None = None
        self.fps = 0.0

    def update(self, timestamp: float) -> float:
        if self.previous is None:
            self.previous = timestamp
            return self.fps
        dt = max(timestamp - self.previous, 1e-6)
        self.previous = timestamp
        instant = 1.0 / dt
        self.fps = instant if self.fps <= 0.0 else (self.alpha * instant + (1.0 - self.alpha) * self.fps)
        return self.fps


def add_detect_gui_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser(
        "detect-gui",
        help="打开 USB 相机并显示纯 YOLO 检测框。",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--devices", help="逗号分隔的相机设备，会覆盖 --left-device/--right-device")
    parser.add_argument("--left-device", help="左相机设备；提供 --devices 时忽略")
    parser.add_argument("--right-device", help="右相机设备；提供 --devices 时忽略")
    parser.add_argument("--width", type=int, default=3840, help="相机采集宽度")
    parser.add_argument("--height", type=int, default=2160, help="相机采集高度")
    parser.add_argument("--fps", type=float, default=30.0, help="相机采集帧率")
    parser.add_argument("--fourcc", default="MJPG", help="相机 FOURCC")
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
    parser.add_argument("--display-width", type=int, default=720, help="每路相机预览宽度")
    parser.add_argument("--warmup-frames", type=int, default=5, help="相机预热帧数")
    parser.add_argument("--window", default="TennisBot YOLO Detect", help="OpenCV 窗口标题")
    parser.add_argument("--dry-run", action="store_true", help="只打印解析后的配置，不打开相机")
    parser.set_defaults(func=cmd_detect_gui)


def cmd_detect_gui(args: argparse.Namespace) -> int:
    devices = parse_devices(args)
    validate_args(args, devices)
    if args.dry_run:
        print("detect_gui=dry-run")
        print(f"devices={','.join(devices)}")
        print(f"model={args.model}")
        print(f"capture={args.width}x{args.height}@{args.fps:g} fourcc={args.fourcc}")
        print(f"tile={args.tile} imgsz={args.imgsz} display_width={args.display_width}")
        return 0

    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "opencv-python is required for detect-gui. Run with "
            "`uv run --extra detect tennisbot-yolo detect-gui ...`."
        ) from exc

    captures = [open_capture(device, args.width, args.height, args.fps, args.fourcc) for device in devices]
    detector = YoloDetector(
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
    )

    cv2.namedWindow(args.window, cv2.WINDOW_NORMAL)
    fps_meter = FpsMeter()
    frame_id = 0
    try:
        for _ in range(max(0, args.warmup_frames)):
            for capture in captures:
                capture.read()

        while True:
            frames = []
            for device, capture in zip(devices, captures, strict=True):
                ok, frame = capture.read()
                if not ok:
                    raise RuntimeError(f"Camera read failed: {device}")
                frames.append(frame)

            timestamp = time.perf_counter()
            detections = detector.detect(frames)
            fps = fps_meter.update(timestamp)
            canvas = render_gui(
                devices,
                frames,
                detections,
                model_path=args.model,
                fps=fps,
                frame_id=frame_id,
                display_width=args.display_width,
                tile=args.tile,
                imgsz=args.imgsz,
            )
            cv2.imshow(args.window, canvas)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            frame_id += 1
    finally:
        for capture in captures:
            capture.release()
        cv2.destroyWindow(args.window)
    return 0


def parse_devices(args: argparse.Namespace) -> list[str]:
    if args.devices:
        devices = [item.strip() for item in str(args.devices).split(",") if item.strip()]
    else:
        devices = [item for item in (args.left_device, args.right_device) if item]
    if not devices:
        devices = list(DEFAULT_DEVICES)
    return devices


def validate_args(args: argparse.Namespace, devices: list[str]) -> None:
    if not devices:
        raise ValueError("provide at least one camera device")
    if len(devices) > 4:
        raise ValueError("detect-gui supports up to four camera devices")
    if len(args.fourcc) != 4:
        raise ValueError("--fourcc must contain exactly four characters, for example MJPG")
    for name in ("width", "height", "imgsz", "display_width", "tile_width", "tile_height"):
        if getattr(args, name) <= 0:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.fps <= 0:
        raise ValueError("--fps must be positive")
    if args.max_detections <= 0:
        raise ValueError("--max-detections must be positive")
    if args.tile_overlap < 0:
        raise ValueError("--tile-overlap must be non-negative")
    if not args.dry_run and not args.model.is_file():
        raise FileNotFoundError(args.model)


def open_capture(device: str, width: int, height: int, fps: float, fourcc: str) -> Any:
    import cv2

    source: int | str = int(device) if device.isdecimal() else device
    capture = cv2.VideoCapture(source, cv2.CAP_V4L2)
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open camera device: {device}")
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*fourcc))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    return capture


def render_gui(
    devices: list[str],
    frames: list[Any],
    detections: list[list[Detection]],
    *,
    model_path: Path,
    fps: float,
    frame_id: int,
    display_width: int,
    tile: bool,
    imgsz: int,
) -> Any:
    import numpy as np

    previews = [
        render_camera_preview(device, frame, frame_detections, display_width)
        for device, frame, frame_detections in zip(devices, frames, detections, strict=True)
    ]
    height = max(preview.shape[0] for preview in previews)
    padded = [pad_to_height(preview, height) for preview in previews]
    panel = render_status_panel(
        height=height,
        width=420,
        devices=devices,
        detections=detections,
        model_path=model_path,
        fps=fps,
        frame_id=frame_id,
        tile=tile,
        imgsz=imgsz,
    )
    return np.hstack([*padded, panel])


def render_camera_preview(device: str, frame: Any, detections: list[Detection], display_width: int) -> Any:
    import cv2

    overlay = frame.copy()
    draw_detections(overlay, detections)
    put(overlay, device, 18, 36, 0.9, (245, 245, 245), 2)
    put(overlay, f"{len(detections)} detection(s)", 18, 72, 0.7, (80, 220, 255), 2)
    return resize_to_width(overlay, display_width)


def render_status_panel(
    *,
    height: int,
    width: int,
    devices: list[str],
    detections: list[list[Detection]],
    model_path: Path,
    fps: float,
    frame_id: int,
    tile: bool,
    imgsz: int,
) -> Any:
    import numpy as np

    panel = np.full((height, width, 3), (24, 28, 32), dtype=np.uint8)
    text = (235, 240, 245)
    muted = (160, 170, 180)
    accent = (80, 220, 255)
    put(panel, "YOLO Detect", 18, 36, 0.85, text, 2)
    put(panel, f"frame {frame_id}   {fps:.1f} fps", 18, 68, 0.58, muted, 1)
    put(panel, f"model: {model_path.name}", 18, 98, 0.54, muted, 1)
    put(panel, f"mode: {'tile' if tile else 'full'}   imgsz={imgsz}", 18, 126, 0.54, muted, 1)
    y = 174
    for device, device_detections in zip(devices, detections, strict=True):
        put(panel, device, 18, y, 0.58, text, 1)
        put(panel, f"{len(device_detections)} detection(s)", 18, y + 28, 0.72, accent, 2)
        for detection in device_detections[:3]:
            put(
                panel,
                f"conf {detection.confidence:.2f}  center {detection.x:.0f},{detection.y:.0f}",
                34,
                y + 56,
                0.46,
                muted,
                1,
            )
            y += 24
        y += 78
    put(panel, "q or Esc exits", 18, max(40, height - 28), 0.54, muted, 1)
    return panel


def draw_detections(frame: Any, detections: list[Detection]) -> None:
    import cv2

    for detection in detections:
        color = (80, 220, 255)
        x1, y1, x2, y2 = (int(round(v)) for v in (detection.x1, detection.y1, detection.x2, detection.y2))
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.circle(frame, (int(round(detection.x)), int(round(detection.y))), 4, color, -1)
        put(frame, f"{detection.confidence:.2f}", x1, max(18, y1 - 6), 0.65, color, 2)


def resize_to_width(frame: Any, width: int) -> Any:
    import cv2

    if frame.shape[1] == width:
        return frame
    scale = width / frame.shape[1]
    height = max(1, int(round(frame.shape[0] * scale)))
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def pad_to_height(frame: Any, height: int) -> Any:
    import numpy as np

    if frame.shape[0] == height:
        return frame
    pad = np.zeros((height - frame.shape[0], frame.shape[1], 3), dtype=frame.dtype)
    return np.vstack([frame, pad])


def put(image: Any, text: str, x: int, y: int, scale: float, color: tuple[int, int, int], thickness: int) -> None:
    import cv2

    cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, thickness, cv2.LINE_AA)


def make_tiles(frame: Any, tile_width: int, tile_height: int, overlap: int) -> Iterable[tuple[Any, int, int]]:
    height, width = frame.shape[:2]
    tile_w = min(width, tile_width)
    tile_h = min(height, tile_height)
    for y in axis_starts(height, tile_h, overlap):
        for x in axis_starts(width, tile_w, overlap):
            yield frame[y : y + tile_h, x : x + tile_w].copy(), x, y


def axis_starts(length: int, tile: int, overlap: int) -> list[int]:
    if tile >= length:
        return [0]
    stride = max(1, tile - overlap)
    starts = list(range(0, length - tile + 1, stride))
    if starts[-1] != length - tile:
        starts.append(length - tile)
    return sorted(set(starts))


def nms_detections(detections: list[Detection], iou_threshold: float) -> list[Detection]:
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
        if all(iou(detection, existing) <= iou_threshold for existing in kept):
            kept.append(detection)
    return kept


def iou(left: Detection, right: Detection) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = left.area + right.area - inter
    return 0.0 if union <= 0.0 else float(inter / union)


def _detections_from_result(result: object, offset_x: int, offset_y: int, class_id_filter: int | None) -> list[Detection]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    xyxy = boxes.xyxy.detach().cpu().tolist()
    confs = boxes.conf.detach().cpu().tolist()
    raw_classes = boxes.cls.detach().cpu().tolist() if getattr(boxes, "cls", None) is not None else [0] * len(confs)
    detections: list[Detection] = []
    for box_xyxy, confidence, class_id in zip(xyxy, confs, raw_classes, strict=True):
        class_id_int = int(class_id)
        if class_id_filter is not None and class_id_int != class_id_filter:
            continue
        x1, y1, x2, y2 = (float(v) for v in box_xyxy)
        detections.append(
            Detection(
                x1=x1 + offset_x,
                y1=y1 + offset_y,
                x2=x2 + offset_x,
                y2=y2 + offset_y,
                confidence=float(confidence),
                class_id=class_id_int,
            )
        )
    return detections
