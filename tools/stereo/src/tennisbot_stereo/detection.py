from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Protocol

import numpy as np

from .types import BallDetection


class BallDetector(Protocol):
    def detect_pair(self, left_frame: np.ndarray, right_frame: np.ndarray) -> tuple[list[BallDetection], list[BallDetection]]:
        ...


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
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "ultralytics is required for YOLO stereo GUI detection. Run with "
                "`uv run --extra detect tennisbot-stereo gui ...`."
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

    def detect_pair(self, left_frame: np.ndarray, right_frame: np.ndarray) -> tuple[list[BallDetection], list[BallDetection]]:
        if self.tile:
            return self._detect_tiled(left_frame), self._detect_tiled(right_frame)

        results = self.model.predict(
            source=[left_frame, right_frame],
            imgsz=self.imgsz,
            conf=self.confidence_threshold,
            iou=self.iou_threshold,
            max_det=self.max_detections,
            device=self.device,
            stream=False,
            verbose=False,
        )
        return (
            detections_from_result(results[0], 0, 0, self.class_id),
            detections_from_result(results[1], 0, 0, self.class_id),
        )

    def _detect_tiled(self, frame: np.ndarray) -> list[BallDetection]:
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
