from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Protocol

import cv2
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


class HsvBallDetector:
    def __init__(
        self,
        *,
        center_roi: float,
        h_min: int,
        h_max: int,
        s_min: int,
        v_min: int,
        min_area: float,
        max_area: float,
        morph_kernel: int,
        max_detections: int,
    ) -> None:
        self.center_roi = float(np.clip(center_roi, 0.05, 1.0))
        self.h_min = int(np.clip(h_min, 0, 179))
        self.h_max = int(np.clip(h_max, 0, 179))
        self.s_min = int(np.clip(s_min, 0, 255))
        self.v_min = int(np.clip(v_min, 0, 255))
        self.min_area = min_area
        self.max_area = max_area
        self.morph_kernel = morph_kernel
        self.max_detections = max_detections

    def detect_pair(self, left_frame: np.ndarray, right_frame: np.ndarray) -> tuple[list[BallDetection], list[BallDetection]]:
        return self.detect_frame(left_frame), self.detect_frame(right_frame)

    def detect_frame(self, frame: np.ndarray) -> list[BallDetection]:
        x0, y0, x1, y1 = center_roi_bounds(frame.shape[1], frame.shape[0], self.center_roi)
        roi = frame[y0:y1, x0:x1]
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        mask = hsv_mask(hsv, self.h_min, self.h_max, self.s_min, self.v_min)

        if self.morph_kernel > 1:
            size = self.morph_kernel if self.morph_kernel % 2 == 1 else self.morph_kernel + 1
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
        detections: list[BallDetection] = []
        for label in range(1, count):
            area = float(stats[label, cv2.CC_STAT_AREA])
            if area < self.min_area or area > self.max_area:
                continue
            bw = float(stats[label, cv2.CC_STAT_WIDTH])
            bh = float(stats[label, cv2.CC_STAT_HEIGHT])
            if bw <= 0.0 or bh <= 0.0:
                continue
            cx, cy = (float(value) for value in centroids[label])
            radius = max(2.0, 0.5 * max(bw, bh))
            fill_ratio = area / max(bw * bh, 1.0)
            area_score = min(1.0, area / max(self.min_area * 8.0, 1.0))
            confidence = float(np.clip(0.45 * area_score + 0.55 * min(1.0, fill_ratio * 1.4), 0.0, 1.0))
            detections.append(
                BallDetection(
                    x1=x0 + cx - radius,
                    y1=y0 + cy - radius,
                    x2=x0 + cx + radius,
                    y2=y0 + cy + radius,
                    confidence=confidence,
                )
            )

        return sorted(detections, key=lambda item: item.confidence, reverse=True)[: self.max_detections]


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


def center_roi_bounds(width: int, height: int, fraction: float) -> tuple[int, int, int, int]:
    fraction = float(np.clip(fraction, 0.05, 1.0))
    roi_width = max(1, int(round(width * fraction)))
    roi_height = max(1, int(round(height * fraction)))
    x0 = max(0, (width - roi_width) // 2)
    y0 = max(0, (height - roi_height) // 2)
    return x0, y0, min(width, x0 + roi_width), min(height, y0 + roi_height)


def hsv_mask(hsv: np.ndarray, h_min: int, h_max: int, s_min: int, v_min: int) -> np.ndarray:
    lower = np.array([h_min, int(np.clip(s_min, 0, 255)), int(np.clip(v_min, 0, 255))], dtype=np.uint8)
    upper = np.array([h_max, 255, 255], dtype=np.uint8)
    if h_min <= h_max:
        return cv2.inRange(hsv, lower, upper)

    low_wrap = cv2.inRange(hsv, np.array([0, lower[1], lower[2]], dtype=np.uint8), upper)
    high_wrap = cv2.inRange(hsv, lower, np.array([179, 255, 255], dtype=np.uint8))
    return cv2.bitwise_or(low_wrap, high_wrap)


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
