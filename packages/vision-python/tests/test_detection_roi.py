from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np

from tennisbot_vision.detection import YoloBallDetector


class FakeTensor:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def detach(self) -> FakeTensor:
        return self

    def cpu(self) -> FakeTensor:
        return self

    def tolist(self) -> list[Any]:
        return self.values


class FakeBoxes:
    def __init__(self, boxes: list[tuple[float, float, float, float]]) -> None:
        self.xyxy = FakeTensor([list(box) for box in boxes])
        self.conf = FakeTensor([0.9 for _ in boxes])
        self.cls = FakeTensor([0 for _ in boxes])
        self._count = len(boxes)

    def __len__(self) -> int:
        return self._count


class FakeResult:
    def __init__(self, boxes: list[tuple[float, float, float, float]]) -> None:
        self.boxes = FakeBoxes(boxes)


class FakeModel:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self._queued_results: list[list[FakeResult]] = []

    def queue(self, *results: FakeResult) -> None:
        self._queued_results.append(list(results))

    def predict(
        self,
        *,
        source: list[np.ndarray],
        imgsz: int,
        conf: float,
        iou: float,
        max_det: int,
        device: str | None,
        stream: bool,
        verbose: bool,
    ) -> list[FakeResult]:
        self.calls.append(
            {
                "source_shapes": [tuple(frame.shape[:2]) for frame in source],
                "imgsz": imgsz,
                "conf": conf,
                "iou": iou,
                "max_det": max_det,
                "device": device,
                "stream": stream,
                "verbose": verbose,
            }
        )
        return self._queued_results.pop(0)


def make_detector(fake_model: FakeModel) -> YoloBallDetector:
    return YoloBallDetector(
        Path("unused.pt"),
        confidence_threshold=0.05,
        iou_threshold=0.5,
        imgsz=640,
        max_detections=6,
        device=None,
        class_id=0,
        tile=False,
        tile_width=2048,
        tile_height=1216,
        tile_overlap=160,
        roi_tracking=True,
        roi_width=100,
        roi_height=80,
        roi_expanded_width=140,
        roi_expanded_height=100,
        search_imgsz=640,
        roi_imgsz=320,
        roi_lost_after_misses=3,
        roi_expand_after_misses=1,
        model=fake_model,
    )


def test_roi_detector_searches_full_frame_then_uses_stereo_matched_roi() -> None:
    fake_model = FakeModel()
    detector = make_detector(fake_model)
    left_frame = np.zeros((200, 400, 3), dtype=np.uint8)
    right_frame = np.zeros((200, 400, 3), dtype=np.uint8)

    fake_model.queue(
        FakeResult([(190, 95, 210, 115)]),
        FakeResult([(170, 95, 190, 115)]),
    )
    left_detections, right_detections = detector.detect_pair(left_frame, right_frame)

    assert fake_model.calls[-1]["source_shapes"] == [(200, 400), (200, 400)]
    assert fake_model.calls[-1]["imgsz"] == 640

    detector.update_pair_tracks(
        SimpleNamespace(
            left_detection=left_detections[0],
            right_detection=right_detections[0],
        )
    )
    status = detector.tracking_status()
    assert status is not None
    assert status["left_update"] == {
        "locked_before": False,
        "locked_after": True,
        "acquired": True,
        "lost": False,
        "detection_used": True,
        "miss_count": 0,
    }

    fake_model.queue(
        FakeResult([(48, 38, 54, 44)]),
        FakeResult([(48, 38, 54, 44)]),
    )
    next_left, next_right = detector.detect_pair(left_frame, right_frame)

    assert fake_model.calls[-1]["source_shapes"] == [(80, 100), (80, 100)]
    assert fake_model.calls[-1]["imgsz"] == 320
    assert next_left[0].x1 == 198
    assert next_left[0].y1 == 103
    assert next_right[0].x1 == 178
    assert next_right[0].y1 == 103


def test_roi_detector_returns_to_full_frame_after_stereo_match_misses() -> None:
    fake_model = FakeModel()
    detector = make_detector(fake_model)
    frame = np.zeros((200, 400, 3), dtype=np.uint8)

    fake_model.queue(
        FakeResult([(190, 95, 210, 115)]),
        FakeResult([(170, 95, 190, 115)]),
    )
    left_detections, right_detections = detector.detect_pair(frame, frame)
    detector.update_pair_tracks(
        SimpleNamespace(
            left_detection=left_detections[0],
            right_detection=right_detections[0],
        )
    )

    for _ in range(3):
        fake_model.queue(FakeResult([]), FakeResult([]))
        detector.detect_pair(frame, frame)
        detector.update_pair_tracks(None)

    status = detector.tracking_status()
    assert status is not None
    assert status["left_update"] == {
        "locked_before": True,
        "locked_after": False,
        "acquired": False,
        "lost": True,
        "detection_used": False,
        "miss_count": 0,
    }

    fake_model.queue(FakeResult([]), FakeResult([]))
    detector.detect_pair(frame, frame)
    assert fake_model.calls[-1]["source_shapes"] == [(200, 400), (200, 400)]
    assert fake_model.calls[-1]["imgsz"] == 640
