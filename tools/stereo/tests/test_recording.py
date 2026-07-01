from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from tennisbot_stereo.recording import StereoRunRecorder
from tennisbot_stereo.types import BallDetection, StereoBallMatch, StereoMatchDiagnostics


def test_stereo_run_recorder_writes_session_points_and_detections(tmp_path: Path) -> None:
    recorder = StereoRunRecorder.create(
        root=tmp_path,
        record_preview_video=False,
        metadata={"capture": {"width": 1280, "height": 720}},
    )
    match = StereoBallMatch(
        left_detection=BallDetection(10, 20, 30, 40, 0.8),
        right_detection=BallDetection(5, 20, 25, 40, 0.7),
        left_rectified=(20.0, 30.0),
        right_rectified=(15.0, 30.2),
        point_3d_m=np.asarray([0.1, 0.2, 2.0], dtype=np.float64),
        disparity_px=5.0,
        epipolar_error_px=0.2,
        reprojection_error_px=0.1,
        confidence=0.7,
        cost=-0.6,
    )

    recorder.record_frame(
        frame_id=7,
        elapsed_sec=1.25,
        timestamp_unix_ms=1770000000000,
        left_detections=[match.left_detection],
        right_detections=[match.right_detection],
        match=match,
        diagnostics=StereoMatchDiagnostics(evaluated_candidate_count=1, best_cost=-0.6),
    )
    recorder.close()

    session = json.loads((recorder.session_dir / "session.json").read_text(encoding="utf-8"))
    assert session["schema_version"] == "tennisbot.stereo_recording.v1"
    assert session["files"]["points"] == "points.ndjson"

    point = json.loads((recorder.session_dir / "points.ndjson").read_text(encoding="utf-8"))
    assert point["frame_id"] == 7
    assert point["position_m"] == {"x": 0.1, "y": 0.2, "z": 2.0}

    detections = json.loads((recorder.session_dir / "detections.ndjson").read_text(encoding="utf-8"))
    assert detections["selected"]["confidence"] == 0.7
    assert detections["diagnostics"]["evaluated_candidate_count"] == 1
