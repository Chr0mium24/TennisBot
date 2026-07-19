from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

import numpy as np

from .types import BallDetection


class BallDetector(Protocol):
    def detect_pair(self, left_frame: np.ndarray, right_frame: np.ndarray) -> tuple[list[BallDetection], list[BallDetection]]:
        ...


@dataclass(frozen=True)
class RoiTrackingConfig:
    roi_width: int = 1024
    roi_height: int = 576
    expanded_width: int = 1280
    expanded_height: int = 720
    search_imgsz: int = 1536
    roi_imgsz: int = 960
    lost_after_misses: int = 3
    expand_after_misses: int = 1
    edge_margin_ratio: float = 0.20
    velocity_alpha: float = 0.60

    def __post_init__(self) -> None:
        for name in (
            "roi_width",
            "roi_height",
            "expanded_width",
            "expanded_height",
            "search_imgsz",
            "roi_imgsz",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.lost_after_misses <= 0:
            raise ValueError("lost_after_misses must be positive")
        if self.expand_after_misses < 0:
            raise ValueError("expand_after_misses must be nonnegative")
        if not 0.0 <= self.edge_margin_ratio < 0.5:
            raise ValueError("edge_margin_ratio must be in [0, 0.5)")
        if not 0.0 <= self.velocity_alpha <= 1.0:
            raise ValueError("velocity_alpha must be in [0, 1]")


@dataclass(frozen=True)
class RoiWindow:
    mode: str
    x1: int
    y1: int
    x2: int
    y2: int
    imgsz: int
    expanded: bool = False

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1

    def to_dict(self) -> dict[str, int | str | bool]:
        return {
            "mode": self.mode,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "width": self.width,
            "height": self.height,
            "imgsz": self.imgsz,
            "expanded": self.expanded,
        }


@dataclass
class _RoiCameraState:
    locked: bool = False
    center_x: float = 0.0
    center_y: float = 0.0
    velocity_x: float = 0.0
    velocity_y: float = 0.0
    miss_count: int = 0
    force_expanded: bool = False


@dataclass(frozen=True)
class RoiTrackUpdate:
    locked_before: bool
    locked_after: bool
    acquired: bool
    lost: bool
    detection_used: bool
    miss_count: int

    def to_dict(self) -> dict[str, bool | int]:
        return {
            "locked_before": self.locked_before,
            "locked_after": self.locked_after,
            "acquired": self.acquired,
            "lost": self.lost,
            "detection_used": self.detection_used,
            "miss_count": self.miss_count,
        }


class _StereoMatchRoiTracker:
    def __init__(self, config: RoiTrackingConfig) -> None:
        self.config = config
        self.state = _RoiCameraState()

    def window(self, frame_width: int, frame_height: int) -> RoiWindow:
        if not self.state.locked:
            return RoiWindow(
                mode="search",
                x1=0,
                y1=0,
                x2=frame_width,
                y2=frame_height,
                imgsz=self.config.search_imgsz,
            )

        predicted_x = self.state.center_x + self.state.velocity_x
        predicted_y = self.state.center_y + self.state.velocity_y
        expanded = self.state.force_expanded or self.state.miss_count >= self.config.expand_after_misses
        width = self.config.expanded_width if expanded else self.config.roi_width
        height = self.config.expanded_height if expanded else self.config.roi_height
        x1, y1, x2, y2 = crop_bounds(predicted_x, predicted_y, width, height, frame_width, frame_height)
        return RoiWindow(
            mode="roi",
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            imgsz=self.config.roi_imgsz,
            expanded=expanded,
        )

    def update(
        self,
        detection: BallDetection | None,
        *,
        frame_width: int,
        frame_height: int,
        window: RoiWindow,
    ) -> RoiTrackUpdate:
        locked_before = self.state.locked
        if detection is None:
            return self._record_miss(locked_before, frame_width, frame_height)

        cx = detection.x
        cy = detection.y
        if self.state.locked:
            raw_vx = cx - self.state.center_x
            raw_vy = cy - self.state.center_y
            alpha = self.config.velocity_alpha
            self.state.velocity_x = alpha * raw_vx + (1.0 - alpha) * self.state.velocity_x
            self.state.velocity_y = alpha * raw_vy + (1.0 - alpha) * self.state.velocity_y
        else:
            self.state.velocity_x = 0.0
            self.state.velocity_y = 0.0

        self.state.locked = True
        self.state.center_x = cx
        self.state.center_y = cy
        self.state.miss_count = 0
        self.state.force_expanded = detection_near_window_edge(detection, window, self.config.edge_margin_ratio)
        return RoiTrackUpdate(
            locked_before=locked_before,
            locked_after=True,
            acquired=not locked_before,
            lost=False,
            detection_used=True,
            miss_count=0,
        )

    def _record_miss(self, locked_before: bool, frame_width: int, frame_height: int) -> RoiTrackUpdate:
        if self.state.locked:
            self.state.center_x = clamp(
                self.state.center_x + self.state.velocity_x,
                0.0,
                float(frame_width),
            )
            self.state.center_y = clamp(
                self.state.center_y + self.state.velocity_y,
                0.0,
                float(frame_height),
            )
            self.state.miss_count += 1
            if self.state.miss_count >= self.config.lost_after_misses:
                self.state = _RoiCameraState()
                return RoiTrackUpdate(
                    locked_before=locked_before,
                    locked_after=False,
                    acquired=False,
                    lost=True,
                    detection_used=False,
                    miss_count=0,
                )

        return RoiTrackUpdate(
            locked_before=locked_before,
            locked_after=self.state.locked,
            acquired=False,
            lost=False,
            detection_used=False,
            miss_count=self.state.miss_count,
        )


class YoloBallDetector:
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
        roi_tracking: bool = False,
        roi_width: int = 1024,
        roi_height: int = 576,
        roi_expanded_width: int = 1280,
        roi_expanded_height: int = 720,
        search_imgsz: int | None = None,
        roi_imgsz: int | None = None,
        roi_lost_after_misses: int = 3,
        roi_expand_after_misses: int = 1,
        roi_edge_margin_ratio: float = 0.20,
        roi_velocity_alpha: float = 0.60,
        model: Any | None = None,
    ) -> None:
        if tile and roi_tracking:
            raise ValueError("tile inference and roi_tracking cannot be enabled together")
        if model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise RuntimeError(
                    "ultralytics is required for online YOLO diagnostics. Run through "
                    "`uv run scripts/test.py ...`."
                ) from exc
            model = YOLO(str(model_path))

        self.model = model
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
        self.roi_tracking = roi_tracking
        self.roi_config = RoiTrackingConfig(
            roi_width=roi_width,
            roi_height=roi_height,
            expanded_width=roi_expanded_width,
            expanded_height=roi_expanded_height,
            search_imgsz=imgsz if search_imgsz is None or search_imgsz <= 0 else search_imgsz,
            roi_imgsz=imgsz if roi_imgsz is None or roi_imgsz <= 0 else roi_imgsz,
            lost_after_misses=roi_lost_after_misses,
            expand_after_misses=roi_expand_after_misses,
            edge_margin_ratio=roi_edge_margin_ratio,
            velocity_alpha=roi_velocity_alpha,
        )
        self._left_roi_tracker = _StereoMatchRoiTracker(self.roi_config)
        self._right_roi_tracker = _StereoMatchRoiTracker(self.roi_config)
        self._last_left_window: RoiWindow | None = None
        self._last_right_window: RoiWindow | None = None
        self._last_left_frame_size: tuple[int, int] | None = None
        self._last_right_frame_size: tuple[int, int] | None = None
        self._last_left_update: RoiTrackUpdate | None = None
        self._last_right_update: RoiTrackUpdate | None = None

    def detect_pair(self, left_frame: np.ndarray, right_frame: np.ndarray) -> tuple[list[BallDetection], list[BallDetection]]:
        if self.tile:
            return self._detect_tiled(left_frame), self._detect_tiled(right_frame)
        if self.roi_tracking:
            return self._detect_pair_with_roi_tracking(left_frame, right_frame)

        results = self._predict([left_frame, right_frame], imgsz=self.imgsz)
        return (
            detections_from_result(results[0], 0, 0, self.class_id),
            detections_from_result(results[1], 0, 0, self.class_id),
        )

    def detect(self, frame: np.ndarray) -> list[BallDetection]:
        """Run one-camera inference without creating a second camera source."""
        if self.tile:
            return self._detect_tiled(frame)
        result = self._predict([frame], imgsz=self.imgsz)[0]
        return detections_from_result(result, 0, 0, self.class_id)

    def _detect_pair_with_roi_tracking(
        self,
        left_frame: np.ndarray,
        right_frame: np.ndarray,
    ) -> tuple[list[BallDetection], list[BallDetection]]:
        left_height, left_width = left_frame.shape[:2]
        right_height, right_width = right_frame.shape[:2]
        left_window = self._left_roi_tracker.window(left_width, left_height)
        right_window = self._right_roi_tracker.window(right_width, right_height)
        self._last_left_window = left_window
        self._last_right_window = right_window
        self._last_left_frame_size = (left_width, left_height)
        self._last_right_frame_size = (right_width, right_height)
        self._last_left_update = None
        self._last_right_update = None

        left_crop = crop_frame(left_frame, left_window)
        right_crop = crop_frame(right_frame, right_window)
        if left_window.imgsz == right_window.imgsz:
            results = self._predict([left_crop, right_crop], imgsz=left_window.imgsz)
            left_result, right_result = results[0], results[1]
        else:
            left_result = self._predict([left_crop], imgsz=left_window.imgsz)[0]
            right_result = self._predict([right_crop], imgsz=right_window.imgsz)[0]

        return (
            detections_from_result(left_result, left_window.x1, left_window.y1, self.class_id),
            detections_from_result(right_result, right_window.x1, right_window.y1, self.class_id),
        )

    def update_pair_tracks(self, match: Any | None) -> None:
        if not self.roi_tracking:
            return
        if (
            self._last_left_window is None
            or self._last_right_window is None
            or self._last_left_frame_size is None
            or self._last_right_frame_size is None
        ):
            return

        left_detection = None if match is None else match.left_detection
        right_detection = None if match is None else match.right_detection
        left_width, left_height = self._last_left_frame_size
        right_width, right_height = self._last_right_frame_size
        self._last_left_update = self._left_roi_tracker.update(
            left_detection,
            frame_width=left_width,
            frame_height=left_height,
            window=self._last_left_window,
        )
        self._last_right_update = self._right_roi_tracker.update(
            right_detection,
            frame_width=right_width,
            frame_height=right_height,
            window=self._last_right_window,
        )

    def tracking_status(self) -> dict[str, object] | None:
        if not self.roi_tracking:
            return None
        return {
            "left_window": None if self._last_left_window is None else self._last_left_window.to_dict(),
            "right_window": None if self._last_right_window is None else self._last_right_window.to_dict(),
            "left_update": None if self._last_left_update is None else self._last_left_update.to_dict(),
            "right_update": None if self._last_right_update is None else self._last_right_update.to_dict(),
        }

    def _predict(self, sources: list[np.ndarray], *, imgsz: int) -> list[Any]:
        return self.model.predict(
            source=sources,
            imgsz=imgsz,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=self.max_detections,
            device=self.device,
            stream=False,
            verbose=False,
        )

    def _detect_tiled(self, frame: np.ndarray) -> list[BallDetection]:
        tiles = list(make_tiles(frame, self.tile_width, self.tile_height, self.tile_overlap))
        results = self._predict([tile for tile, _, _ in tiles], imgsz=self.imgsz)
        detections: list[BallDetection] = []
        for result, (_, offset_x, offset_y) in zip(results, tiles, strict=True):
            detections.extend(detections_from_result(result, offset_x, offset_y, self.class_id))
        return nms_detections(detections, self.iou_threshold)[: self.max_detections]


def make_tiles(frame: np.ndarray, tile_width: int, tile_height: int, overlap: int) -> Iterable[tuple[np.ndarray, int, int]]:
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


def crop_frame(frame: np.ndarray, window: RoiWindow) -> np.ndarray:
    if window.mode == "search":
        return frame
    return frame[window.y1 : window.y2, window.x1 : window.x2].copy()


def crop_bounds(
    cx: float,
    cy: float,
    crop_width: int,
    crop_height: int,
    frame_width: int,
    frame_height: int,
) -> tuple[int, int, int, int]:
    crop_width = min(crop_width, frame_width)
    crop_height = min(crop_height, frame_height)
    x1 = int(round(cx - crop_width / 2.0))
    y1 = int(round(cy - crop_height / 2.0))
    x1 = min(max(0, x1), frame_width - crop_width)
    y1 = min(max(0, y1), frame_height - crop_height)
    return x1, y1, x1 + crop_width, y1 + crop_height


def detection_near_window_edge(detection: BallDetection, window: RoiWindow, edge_margin_ratio: float) -> bool:
    if window.mode != "roi" or window.width <= 0 or window.height <= 0:
        return False
    local_x = (detection.x - window.x1) / window.width
    local_y = (detection.y - window.y1) / window.height
    margin = edge_margin_ratio
    return local_x <= margin or local_x >= 1.0 - margin or local_y <= margin or local_y >= 1.0 - margin


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def nms_detections(detections: list[BallDetection], iou_threshold: float) -> list[BallDetection]:
    kept: list[BallDetection] = []
    for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
        if all(iou(detection, existing) <= iou_threshold for existing in kept):
            kept.append(detection)
    return kept


def iou(left: BallDetection, right: BallDetection) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = left.area + right.area - inter
    return 0.0 if union <= 0.0 else float(inter / union)


def detections_from_result(
    result: Any,
    offset_x: int,
    offset_y: int,
    class_id_filter: int | None,
) -> list[BallDetection]:
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return []

    xyxy = boxes.xyxy.detach().cpu().tolist()
    confs = boxes.conf.detach().cpu().tolist()
    raw_classes = boxes.cls.detach().cpu().tolist() if getattr(boxes, "cls", None) is not None else [0] * len(confs)
    detections: list[BallDetection] = []
    for box_xyxy, confidence, class_id in zip(xyxy, confs, raw_classes, strict=True):
        class_id_int = int(class_id)
        if class_id_filter is not None and class_id_int != class_id_filter:
            continue
        x1, y1, x2, y2 = (float(v) for v in box_xyxy)
        detections.append(
            BallDetection(
                x1=x1 + offset_x,
                y1=y1 + offset_y,
                x2=x2 + offset_x,
                y2=y2 + offset_y,
                confidence=float(confidence),
                class_id=class_id_int,
            )
        )
    return detections
