from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, TextIO

import cv2
import numpy as np

from tennisbot_camera.capture import CapturedFrame


class TestRecordingSink:
    """Records frames already owned by a test loop; it never opens a camera."""

    __test__ = False

    def __init__(
        self,
        *,
        root: Path,
        session_name: str | None,
        camera_ids: tuple[str, ...],
        fps: float,
        frame_size: tuple[int, int],
        overlay: bool,
        test_kind: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        name = session_name or now.astimezone().strftime("test_%Y%m%d_%H%M%S_%Z")
        self.session_dir = unique_dir(root / name)
        self.session_dir.mkdir(parents=True)
        self.camera_ids = camera_ids
        self.writers = {
            camera_id: video_writer(self.session_dir / f"{camera_id}.mp4", fps, frame_size)
            for camera_id in camera_ids
        }
        self.overlay_writer = None
        self.overlay_requested = overlay
        self.fps = fps
        self.frames_file = opened(self.session_dir / "frames.ndjson")
        self.pairs_file = opened(self.session_dir / "pairs.ndjson") if len(camera_ids) == 2 else None
        self.detections_file = opened(self.session_dir / "detections.ndjson")
        self.triangulation_file = opened(self.session_dir / "triangulation.ndjson") if test_kind == "triangulation" else None
        payload = {
            "schema_version": "tennisbot.test_recording.session.v1",
            "created_at": now.isoformat(),
            "test_kind": test_kind,
            "mode": "stereo" if len(camera_ids) == 2 else "mono",
            "camera_ids": list(camera_ids),
            "streams": {camera_id: f"{camera_id}.mp4" for camera_id in camera_ids},
            "files": {
                "frames": "frames.ndjson",
                "pairs": "pairs.ndjson" if len(camera_ids) == 2 else None,
                "detections": "detections.ndjson",
                "triangulation": "triangulation.ndjson" if test_kind == "triangulation" else None,
                "overlay": "overlay.mp4" if overlay else None,
            },
            "capture": {"fps": fps, "width": frame_size[0], "height": frame_size[1]},
        }
        (self.session_dir / "session.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def record_mono(self, frame: CapturedFrame, detections: list[dict[str, Any]], overlay: np.ndarray | None = None) -> None:
        self.writers[frame.camera_id].write(frame.image)
        self.frames_file.write(json.dumps(frame_payload(frame), sort_keys=True) + "\n")
        self.detections_file.write(json.dumps({"sequence": frame.sequence, "camera_id": frame.camera_id, "detections": detections}, sort_keys=True) + "\n")
        if overlay is not None and self.overlay_requested:
            self._ensure_overlay_writer(overlay)
            assert self.overlay_writer is not None
            self.overlay_writer.write(overlay)

    def record_stereo(
        self,
        pair_id: int,
        left: CapturedFrame,
        right: CapturedFrame,
        delta_ns: int,
        detections: dict[str, list[dict[str, Any]]],
        triangulation: dict[str, Any] | None,
        overlay: np.ndarray | None = None,
    ) -> None:
        for frame in (left, right):
            self.writers[frame.camera_id].write(frame.image)
            self.frames_file.write(json.dumps(frame_payload(frame), sort_keys=True) + "\n")
        assert self.pairs_file is not None
        self.pairs_file.write(json.dumps({"pair_id": pair_id, "left_sequence": left.sequence, "right_sequence": right.sequence, "delta_ms": delta_ns / 1e6}, sort_keys=True) + "\n")
        self.detections_file.write(json.dumps({"pair_id": pair_id, **detections}, sort_keys=True) + "\n")
        if triangulation is not None and self.triangulation_file is not None:
            self.triangulation_file.write(json.dumps({"pair_id": pair_id, **triangulation}, sort_keys=True) + "\n")
        if overlay is not None and self.overlay_requested:
            self._ensure_overlay_writer(overlay)
            assert self.overlay_writer is not None
            self.overlay_writer.write(overlay)

    def _ensure_overlay_writer(self, overlay: np.ndarray) -> None:
        if self.overlay_writer is None:
            self.overlay_writer = video_writer(
                self.session_dir / "overlay.mp4",
                self.fps,
                (int(overlay.shape[1]), int(overlay.shape[0])),
            )

    def close(self) -> None:
        for writer in self.writers.values():
            writer.release()
        if self.overlay_writer is not None:
            self.overlay_writer.release()
        for stream in (self.frames_file, self.pairs_file, self.detections_file, self.triangulation_file):
            if stream is not None:
                stream.close()


def frame_payload(frame: CapturedFrame) -> dict[str, Any]:
    return {"camera_id": frame.camera_id, "sequence": frame.sequence, "monotonic_ns": frame.monotonic_ns, "unix_ns": frame.unix_ns}


def detection_payload(detection: Any) -> dict[str, Any]:
    return {"bbox": [detection.x1, detection.y1, detection.x2, detection.y2], "center": [detection.x, detection.y], "confidence": detection.confidence, "class_id": detection.class_id}


def video_writer(path: Path, fps: float, frame_size: tuple[int, int]) -> cv2.VideoWriter:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), max(fps, 1.0), frame_size)
    if not writer.isOpened():
        raise RuntimeError(f"cannot open video writer: {path}")
    return writer


def opened(path: Path) -> TextIO:
    return path.open("a", encoding="utf-8", buffering=1)


def unique_dir(path: Path) -> Path:
    if not path.exists():
        return path
    index = 2
    while (candidate := path.with_name(f"{path.name}_{index}")).exists():
        index += 1
    return candidate
