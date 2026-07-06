from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, TextIO

import cv2
import numpy as np

from .types import BallDetection, StereoBallMatch, StereoMatchDiagnostics


@dataclass(frozen=True)
class StereoRunRecorder:
    session_dir: Path
    points_file: TextIO
    detections_file: TextIO
    preview_path: Path | None = None
    preview_writer: cv2.VideoWriter | None = None

    @classmethod
    def create(
        cls,
        *,
        root: Path,
        metadata: dict[str, Any],
        record_preview_video: bool,
    ) -> StereoRunRecorder:
        created_at = datetime.now(timezone.utc)
        session_id = created_at.astimezone().strftime("stereo_%Y%m%d_%H%M%S_%Z")
        session_dir = unique_session_dir(root, session_id)
        session_dir.mkdir(parents=True)
        session_payload = {
            "schema_version": "tennisbot.stereo_recording.v1",
            "session_id": session_dir.name,
            "created_at": created_at.isoformat(),
            "coordinate_frame": "left_camera: x right, y down, z forward",
            "files": {
                "points": "points.ndjson",
                "detections": "detections.ndjson",
                **({"preview_video": "preview.mp4"} if record_preview_video else {}),
            },
            **metadata,
        }
        (session_dir / "session.json").write_text(json.dumps(session_payload, indent=2), encoding="utf-8")
        return cls(
            session_dir=session_dir,
            points_file=(session_dir / "points.ndjson").open("a", encoding="utf-8", buffering=1),
            detections_file=(session_dir / "detections.ndjson").open("a", encoding="utf-8", buffering=1),
            preview_path=session_dir / "preview.mp4" if record_preview_video else None,
        )

    def record_frame(
        self,
        *,
        frame_id: int,
        elapsed_sec: float,
        timestamp_unix_ms: int,
        left_detections: list[BallDetection],
        right_detections: list[BallDetection],
        match: StereoBallMatch | None,
        diagnostics: StereoMatchDiagnostics,
    ) -> None:
        detections_payload = {
            "frame_id": frame_id,
            "elapsed_sec": elapsed_sec,
            "timestamp_unix_ms": timestamp_unix_ms,
            "left": [detection_payload(detection) for detection in left_detections],
            "right": [detection_payload(detection) for detection in right_detections],
            "selected": None if match is None else selected_match_payload(match),
            "diagnostics": diagnostics_payload(diagnostics),
        }
        self.detections_file.write(json.dumps(detections_payload) + "\n")

        if match is None:
            return
        point_payload = {
            "frame_id": frame_id,
            "elapsed_sec": elapsed_sec,
            "timestamp_unix_ms": timestamp_unix_ms,
            "position_m": {
                "x": float(match.point_3d_m[0]),
                "y": float(match.point_3d_m[1]),
                "z": float(match.point_3d_m[2]),
            },
            "confidence": match.confidence,
            "disparity_px": match.disparity_px,
            "epipolar_error_px": match.epipolar_error_px,
            "reprojection_error_px": match.reprojection_error_px,
            "cost": match.cost,
        }
        self.points_file.write(json.dumps(point_payload) + "\n")

    def record_preview(self, canvas: np.ndarray, fps: float) -> None:
        if self.preview_path is None:
            return
        writer = self.preview_writer
        if writer is None:
            height, width = canvas.shape[:2]
            writer = cv2.VideoWriter(
                str(self.preview_path),
                cv2.VideoWriter_fourcc(*"mp4v"),
                max(fps, 1.0),
                (width, height),
            )
            object.__setattr__(self, "preview_writer", writer)
        writer.write(canvas)

    def close(self) -> None:
        self.points_file.close()
        self.detections_file.close()
        if self.preview_writer is not None:
            self.preview_writer.release()


def unique_session_dir(root: Path, session_id: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    candidate = root / session_id
    if not candidate.exists():
        return candidate
    for index in range(1, 1000):
        candidate = root / f"{session_id}_{index:03d}"
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"cannot allocate session directory under {root}")


def detection_payload(detection: BallDetection) -> dict[str, float | int]:
    return {
        "x1": detection.x1,
        "y1": detection.y1,
        "x2": detection.x2,
        "y2": detection.y2,
        "x": detection.x,
        "y": detection.y,
        "confidence": detection.confidence,
        "class_id": detection.class_id,
    }


def selected_match_payload(match: StereoBallMatch) -> dict[str, Any]:
    return {
        "left_rectified": {"x": match.left_rectified[0], "y": match.left_rectified[1]},
        "right_rectified": {"x": match.right_rectified[0], "y": match.right_rectified[1]},
        "position_m": {
            "x": float(match.point_3d_m[0]),
            "y": float(match.point_3d_m[1]),
            "z": float(match.point_3d_m[2]),
        },
        "confidence": match.confidence,
        "disparity_px": match.disparity_px,
        "epipolar_error_px": match.epipolar_error_px,
        "reprojection_error_px": match.reprojection_error_px,
        "cost": match.cost,
    }


def diagnostics_payload(diagnostics: StereoMatchDiagnostics) -> dict[str, object]:
    return {
        "evaluated_candidate_count": diagnostics.evaluated_candidate_count,
        "rejected_by_epipolar_count": diagnostics.rejected_by_epipolar_count,
        "rejected_by_disparity_count": diagnostics.rejected_by_disparity_count,
        "rejected_by_triangulation_count": diagnostics.rejected_by_triangulation_count,
        "rejected_by_depth_count": diagnostics.rejected_by_depth_count,
        "best_cost": diagnostics.best_cost,
        "candidates": diagnostics.candidates,
    }
