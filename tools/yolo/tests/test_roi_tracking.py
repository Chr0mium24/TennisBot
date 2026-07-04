from __future__ import annotations

from dataclasses import dataclass

from tennisbot_yolo.roi_tracking import CropWindow, RoiTrackConfig, StatefulRoiTracker, detection_near_window_edge


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    conf: float = 0.9


def test_tracker_starts_in_search_and_locks_on_detection() -> None:
    tracker = StatefulRoiTracker(
        RoiTrackConfig(roi_width=960, roi_height=540, roi_imgsz=320, acquire_confirmation_frames=1)
    )

    first = tracker.window(3840, 2160)
    assert first.mode == "search"
    assert first.imgsz == 320

    update = tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=first)
    assert update.acquired is True
    assert update.locked_after is True

    second = tracker.window(3840, 2160)
    assert second.mode == "roi"
    assert second.width == 960
    assert second.height == 540
    assert second.x1 <= 1010 <= second.x2
    assert second.y1 <= 710 <= second.y2


def test_tracker_uses_velocity_for_next_window() -> None:
    tracker = StatefulRoiTracker(RoiTrackConfig(velocity_alpha=1.0, acquire_confirmation_frames=1))
    search = tracker.window(3840, 2160)
    tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=search)
    first_roi = tracker.window(3840, 2160)
    tracker.update([Box(1100, 700, 1120, 720)], frame_width=3840, frame_height=2160, window=first_roi)

    predicted = tracker.window(3840, 2160)
    assert predicted.x1 <= 1210 <= predicted.x2


def test_tracker_expands_after_edge_detection() -> None:
    tracker = StatefulRoiTracker(
        RoiTrackConfig(
            roi_width=960,
            roi_height=540,
            expanded_width=1280,
            expanded_height=720,
            edge_margin_ratio=0.2,
            acquire_confirmation_frames=1,
        )
    )
    search = tracker.window(3840, 2160)
    tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=search)
    roi = tracker.window(3840, 2160)
    near_right_edge = Box(roi.x2 - 20, 700, roi.x2 - 10, 710)

    assert detection_near_window_edge(near_right_edge, roi, 0.2)
    tracker.update([near_right_edge], frame_width=3840, frame_height=2160, window=roi)

    expanded = tracker.window(3840, 2160)
    assert expanded.expanded is True
    assert expanded.width == 1280
    assert expanded.height == 720


def test_tracker_returns_to_search_after_misses() -> None:
    tracker = StatefulRoiTracker(RoiTrackConfig(lost_after_misses=2, acquire_confirmation_frames=1))
    search = tracker.window(3840, 2160)
    tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=search)

    miss_one = tracker.update([], frame_width=3840, frame_height=2160, window=tracker.window(3840, 2160))
    assert miss_one.locked_after is True
    miss_two = tracker.update([], frame_width=3840, frame_height=2160, window=tracker.window(3840, 2160))
    assert miss_two.lost is True

    assert tracker.window(3840, 2160).mode == "search"


def test_edge_check_ignores_search_window() -> None:
    window = CropWindow(mode="search", x1=0, y1=0, x2=3840, y2=2160, imgsz=320)
    assert not detection_near_window_edge(Box(1, 1, 10, 10), window, 0.2)


def test_tracker_confirms_search_candidate_before_locking() -> None:
    tracker = StatefulRoiTracker(RoiTrackConfig(acquire_confirmation_frames=2))
    search = tracker.window(3840, 2160)

    first = tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=search)
    assert first.acquired is False
    assert first.locked_after is False

    second = tracker.update([Box(1012, 706, 1032, 726)], frame_width=3840, frame_height=2160, window=search)
    assert second.acquired is True
    assert second.locked_after is True


def test_tracker_requires_confirmation_for_far_locked_candidate() -> None:
    tracker = StatefulRoiTracker(
        RoiTrackConfig(
            acquire_confirmation_frames=1,
            candidate_confirmation_frames=2,
            max_update_distance_ratio=0.10,
            lost_after_misses=3,
        )
    )
    search = tracker.window(3840, 2160)
    tracker.update([Box(1000, 700, 1020, 720)], frame_width=3840, frame_height=2160, window=search)
    roi = tracker.window(3840, 2160)

    far = Box(1800, 1200, 1820, 1220, conf=0.99)
    first_far = tracker.update([far], frame_width=3840, frame_height=2160, window=roi)
    assert first_far.detection_used is False
    assert first_far.locked_after is True
    assert first_far.miss_count == 1

    second_far = tracker.update([Box(1808, 1204, 1828, 1224, conf=0.99)], frame_width=3840, frame_height=2160, window=roi)
    assert second_far.detection_used is True
    assert second_far.locked_after is True
    assert second_far.miss_count == 0
