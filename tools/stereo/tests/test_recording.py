from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from pytest import MonkeyPatch

from tennisbot_stereo import raw_recording
from tennisbot_stereo.cli import main as stereo_main
from tennisbot_stereo.raw_recording import FrameTimestamp, RawStereoVideoRecorder
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


def test_raw_stereo_video_recorder_writes_session_frames_and_pairs(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    writers: list[DummyWriter] = []

    def fake_create_video_writer(path: Path, *, fps: float, frame_size: tuple[int, int]) -> DummyWriter:
        writer = DummyWriter(path=path, fps=fps, frame_size=frame_size)
        writers.append(writer)
        return writer

    monkeypatch.setattr(raw_recording, "create_video_writer", fake_create_video_writer)
    recorder = RawStereoVideoRecorder.create(
        root=tmp_path,
        metadata={"capture": {"left_device": "/dev/video0", "right_device": "/dev/video2"}},
        fps=30.0,
        frame_size=(4, 3),
        soft_sync_threshold_ms=25.0,
    )
    left_frame = np.zeros((3, 4, 3), dtype=np.uint8)
    right_frame = np.ones((3, 4, 3), dtype=np.uint8)

    recorder.record_pair(
        pair_id=2,
        left_frame=left_frame,
        right_frame=right_frame,
        left_timestamp=FrameTimestamp(monotonic_ns=1_000_000, unix_ns=1_770_000_000_000_000_000, elapsed_sec=0.001),
        right_timestamp=FrameTimestamp(monotonic_ns=2_500_000, unix_ns=1_770_000_000_001_500_000, elapsed_sec=0.0025),
    )
    recorder.close()

    session = json.loads((recorder.session_dir / "session.json").read_text(encoding="utf-8"))
    assert session["schema_version"] == "tennisbot.raw_stereo_recording.v1"
    assert session["files"]["left_video"] == "left.mp4"
    assert session["capture"]["right_device"] == "/dev/video2"
    assert session["soft_sync"]["threshold_ms"] == 25.0

    frames = [
        json.loads(line)
        for line in (recorder.session_dir / "frames.ndjson").read_text(encoding="utf-8").splitlines()
    ]
    assert [(frame["side"], frame["frame_index"]) for frame in frames] == [("left", 2), ("right", 2)]
    assert frames[0]["width"] == 4
    assert frames[0]["height"] == 3

    pair = json.loads((recorder.session_dir / "pairs.ndjson").read_text(encoding="utf-8"))
    assert pair["pair_id"] == 2
    assert pair["delta_ms"] == 1.5
    assert pair["within_soft_sync_threshold"] is True
    assert [writer.frame_shapes for writer in writers] == [[(3, 4, 3)], [(3, 4, 3)]]
    assert all(writer.released for writer in writers)


def test_record_dry_run_uses_current_defaults(capsys) -> None:
    exit_code = stereo_main(["record", "--dry-run"])

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "stereo_record=dry-run" in output
    assert "devices=/dev/video0,/dev/video2" in output
    assert "capture=3840x2160@30 fourcc=MJPG" in output
    assert "duration=unlimited" in output
    assert "preview_width=720" in output
    assert "runs/raw-stereo" in output


class DummyWriter:
    def __init__(self, *, path: Path, fps: float, frame_size: tuple[int, int]) -> None:
        self.path = path
        self.fps = fps
        self.frame_size = frame_size
        self.frame_shapes: list[tuple[int, ...]] = []
        self.released = False

    def write(self, frame: np.ndarray) -> None:
        self.frame_shapes.append(tuple(frame.shape))

    def release(self) -> None:
        self.released = True
