from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, TextIO

import cv2
import numpy as np

from .recording import unique_session_dir


@dataclass(frozen=True)
class RawStereoVideoRecorder:
    session_dir: Path
    left_writer: cv2.VideoWriter
    right_writer: cv2.VideoWriter
    frames_file: TextIO
    pairs_file: TextIO
    soft_sync_threshold_ms: float

    @classmethod
    def create(
        cls,
        *,
        root: Path,
        metadata: dict[str, Any],
        fps: float,
        frame_size: tuple[int, int],
        soft_sync_threshold_ms: float,
    ) -> RawStereoVideoRecorder:
        created_at = datetime.now(timezone.utc)
        session_id = created_at.astimezone().strftime("raw_stereo_%Y%m%d_%H%M%S_%Z")
        session_dir = unique_session_dir(root, session_id)
        session_dir.mkdir(parents=True)
        session_payload = {
            "schema_version": "tennisbot.raw_stereo_recording.v1",
            "session_id": session_dir.name,
            "created_at": created_at.isoformat(),
            "files": {
                "left_video": "left.mp4",
                "right_video": "right.mp4",
                "frames": "frames.ndjson",
                "pairs": "pairs.ndjson",
            },
            "video": {
                "codec": "mp4v",
                "fps": float(fps),
                "width": int(frame_size[0]),
                "height": int(frame_size[1]),
            },
            "soft_sync": {
                "method": "sequential_read_timestamp_pairing",
                "threshold_ms": float(soft_sync_threshold_ms),
            },
            **metadata,
        }
        (session_dir / "session.json").write_text(json.dumps(session_payload, indent=2) + "\n", encoding="utf-8")
        left_writer = create_video_writer(session_dir / "left.mp4", fps=fps, frame_size=frame_size)
        right_writer = create_video_writer(session_dir / "right.mp4", fps=fps, frame_size=frame_size)
        return cls(
            session_dir=session_dir,
            left_writer=left_writer,
            right_writer=right_writer,
            frames_file=(session_dir / "frames.ndjson").open("a", encoding="utf-8", buffering=1),
            pairs_file=(session_dir / "pairs.ndjson").open("a", encoding="utf-8", buffering=1),
            soft_sync_threshold_ms=float(soft_sync_threshold_ms),
        )

    def record_pair(
        self,
        *,
        pair_id: int,
        left_frame: np.ndarray,
        right_frame: np.ndarray,
        left_timestamp: FrameTimestamp,
        right_timestamp: FrameTimestamp,
    ) -> None:
        self.left_writer.write(left_frame)
        self.right_writer.write(right_frame)
        self.frames_file.write(json.dumps(frame_payload("left", pair_id, left_timestamp, left_frame)) + "\n")
        self.frames_file.write(json.dumps(frame_payload("right", pair_id, right_timestamp, right_frame)) + "\n")
        delta_ms = abs(left_timestamp.monotonic_ns - right_timestamp.monotonic_ns) / 1_000_000.0
        self.pairs_file.write(
            json.dumps(
                {
                    "pair_id": int(pair_id),
                    "left_frame_index": int(pair_id),
                    "right_frame_index": int(pair_id),
                    "delta_ms": float(delta_ms),
                    "within_soft_sync_threshold": bool(delta_ms <= self.soft_sync_threshold_ms),
                }
            )
            + "\n"
        )

    def close(self) -> None:
        self.left_writer.release()
        self.right_writer.release()
        self.frames_file.close()
        self.pairs_file.close()


@dataclass(frozen=True)
class FrameTimestamp:
    monotonic_ns: int
    unix_ns: int
    elapsed_sec: float


def create_video_writer(path: Path, *, fps: float, frame_size: tuple[int, int]) -> cv2.VideoWriter:
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        max(float(fps), 1.0),
        (int(frame_size[0]), int(frame_size[1])),
    )
    if not writer.isOpened():
        raise RuntimeError(f"cannot open video writer: {path}")
    return writer


def frame_payload(side: str, frame_index: int, timestamp: FrameTimestamp, frame: np.ndarray) -> dict[str, Any]:
    height, width = frame.shape[:2]
    return {
        "side": side,
        "frame_index": int(frame_index),
        "monotonic_ns": int(timestamp.monotonic_ns),
        "unix_ns": int(timestamp.unix_ns),
        "elapsed_sec": float(timestamp.elapsed_sec),
        "width": int(width),
        "height": int(height),
    }
