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
