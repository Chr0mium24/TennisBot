from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DetectionLike(Protocol):
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float


@dataclass(frozen=True)
class RoiTrackConfig:
    roi_width: int = 960
    roi_height: int = 540
    expanded_width: int = 1280
    expanded_height: int = 720
    search_imgsz: int = 320
    roi_imgsz: int = 320
    lost_after_misses: int = 3
    expand_after_misses: int = 1
    edge_margin_ratio: float = 0.20
    velocity_alpha: float = 0.60
    min_lock_confidence: float = 0.05

    def __post_init__(self) -> None:
        for name in ("roi_width", "roi_height", "expanded_width", "expanded_height", "search_imgsz", "roi_imgsz"):
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
class CropWindow:
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


@dataclass
class RoiTrackState:
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


class StatefulRoiTracker:
    def __init__(self, config: RoiTrackConfig | None = None) -> None:
        self.config = config or RoiTrackConfig()
        self.state = RoiTrackState()

    def window(self, frame_width: int, frame_height: int) -> CropWindow:
        if not self.state.locked:
            return CropWindow(
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
        return CropWindow(
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
        detections: list[DetectionLike],
        *,
        frame_width: int,
        frame_height: int,
        window: CropWindow,
    ) -> RoiTrackUpdate:
        locked_before = self.state.locked
        usable = [item for item in detections if item.conf >= self.config.min_lock_confidence]
        best = max(usable, key=lambda item: item.conf, default=None)
        if best is None:
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
                    self.state = RoiTrackState()
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

        cx = 0.5 * (best.x1 + best.x2)
        cy = 0.5 * (best.y1 + best.y2)
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
        self.state.force_expanded = detection_near_window_edge(best, window, self.config.edge_margin_ratio)
        return RoiTrackUpdate(
            locked_before=locked_before,
            locked_after=True,
            acquired=not locked_before,
            lost=False,
            detection_used=True,
            miss_count=0,
        )


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


def detection_near_window_edge(detection: DetectionLike, window: CropWindow, edge_margin_ratio: float) -> bool:
    if window.mode != "roi" or window.width <= 0 or window.height <= 0:
        return False
    cx = 0.5 * (detection.x1 + detection.x2)
    cy = 0.5 * (detection.y1 + detection.y2)
    local_x = (cx - window.x1) / window.width
    local_y = (cy - window.y1) / window.height
    margin = edge_margin_ratio
    return local_x <= margin or local_x >= 1.0 - margin or local_y <= margin or local_y >= 1.0 - margin


def clamp(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)
