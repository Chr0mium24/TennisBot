import json
from pathlib import Path

import numpy as np

from tennisbot_camera.capture import CapturedFrame
from tennisbot_vision.cli import main
from tennisbot_camera.recording import TestRecordingSink


class Writer:
    def __init__(self) -> None:
        self.frames = 0
        self.closed = False

    def write(self, _frame) -> None:
        self.frames += 1

    def release(self) -> None:
        self.closed = True


def test_online_dry_run_contract(capsys) -> None:
    assert main(["yolo", "mono", "cam2", "--dry-run", "--record-overlay"]) == 0
    output = capsys.readouterr().out
    assert '"devices": ["/dev/video2"]' in output
    assert '"record": true' in output
    assert '"record_overlay": true' in output
    assert main(["triangulation", "stereo", "--dry-run"]) == 0


def test_replay_stereo_dry_run_contract(capsys) -> None:
    assert main([
        "replay",
        "stereo",
        "--recording",
        "runs/recording/20260717_155414",
        "--calibration-package",
        "artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST",
        "--frame-start",
        "75",
        "--frame-end",
        "85",
        "--sync",
        "frame-index",
        "--record-overlay",
        "--dry-run",
    ]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["test"] == "replay"
    assert payload["mode"] == "stereo"
    assert payload["recording"] == "runs/recording/20260717_155414"
    assert payload["calibration_package"] == "artifacts/calibration/stereo_cam1_cam2_20260717_174628_CST"
    assert payload["frame_start"] == 75
    assert payload["frame_end"] == 85
    assert payload["sync"] == "frame-index"
    assert payload["record"] is True
    assert payload["record_overlay"] is True


def test_resolve_stereo_videos_uses_recording_session_streams(tmp_path: Path) -> None:
    from tennisbot_vision.offline_replay import resolve_stereo_videos

    left = tmp_path / "left.mkv"
    right = tmp_path / "right.mkv"
    left.write_bytes(b"left")
    right.write_bytes(b"right")
    (tmp_path / "session.json").write_text(json.dumps({
        "streams": {
            "cam1": {"file": left.name},
            "cam2": {"file": right.name},
        },
    }))

    resolved = resolve_stereo_videos(recording=tmp_path, left_video=None, right_video=None)

    assert resolved.left_video == left
    assert resolved.right_video == right
    assert resolved.recording == tmp_path


def test_recording_sink_consumes_owned_frames_without_camera(monkeypatch, tmp_path: Path) -> None:
    writers: list[Writer] = []

    def make_writer(*_args, **_kwargs) -> Writer:
        writer = Writer()
        writers.append(writer)
        return writer

    monkeypatch.setattr("tennisbot_camera.recording.video_writer", make_writer)
    sink = TestRecordingSink(root=tmp_path, session_name="fixture", camera_ids=("cam1", "cam2"),
        fps=30, frame_size=(4, 3), overlay=True, test_kind="triangulation")
    image = np.zeros((3, 4, 3), dtype=np.uint8)
    left = CapturedFrame("cam1", 0, 10, 20, image)
    right = CapturedFrame("cam2", 0, 12, 22, image)
    sink.record_stereo(0, left, right, 2, {"cam1": [], "cam2": []}, {"x_m": 1}, image)
    sink.close()

    assert [writer.frames for writer in writers] == [1, 1, 1]
    assert all(writer.closed for writer in writers)
    assert (sink.session_dir / "pairs.ndjson").read_text().strip()
    assert (sink.session_dir / "triangulation.ndjson").read_text().strip()
