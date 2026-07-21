import json
from pathlib import Path

import numpy as np
import pytest

from tennisbot_camera.capture import CapturedFrame
from tennisbot_vision.cli import main
from tennisbot_camera.recording import TestRecordingSink
from tennisbot_vision.communication import (
    RawTargetPublishOptions,
    parse_raw_target_publish_options,
    publish_raw_target,
)


class Writer:
    def __init__(self) -> None:
        self.frames = 0
        self.closed = False

    def write(self, _frame) -> None:
        self.frames += 1

    def release(self) -> None:
        self.closed = True


def test_parse_publish_raw_target_options() -> None:
    options = parse_raw_target_publish_options([
        "--task-id", "12", "--sequence-id", "7", "--target-x", "1.25", "--target-y", "-0.5",
        "--predicted-t-remain", "1.5", "--sigma-x", "0.1", "--sigma-y", "0.2", "--dry-run"
    ])
    assert options.task_id == 12
    assert options.sequence_id == 7
    assert options.target_x == 1.25
    assert options.target_y == -0.5
    assert options.predicted_t_remain == 1.5
    assert options.sigma_x == 0.1
    assert options.sigma_y == 0.2
    assert options.dry_run is True

    with pytest.raises(ValueError, match="absolute ROS topic"):
        parse_raw_target_publish_options(["--topic", "target/raw"])
    with pytest.raises(ValueError, match="less than"):
        parse_raw_target_publish_options(["--capture-stamp-nanosec", "1000000000"])
    with pytest.raises(ValueError, match="uint32"):
        parse_raw_target_publish_options(["--sequence-id", "4294967296"])
    with pytest.raises(ValueError, match=r"\(0, 5]"):
        parse_raw_target_publish_options(["--predicted-t-remain", "0"])


def test_publish_raw_target_dry_run_has_complete_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr("tennisbot_vision.communication.time.time_ns", lambda: 1_750_000_000_123_456_789)
    options = RawTargetPublishOptions(
        task_id=4, sequence_id=9, target_x=1.0, target_y=-2.0,
        predicted_t_remain=1.25, sigma_x=0.1, sigma_y=0.2, dry_run=True, auto_source=False,
    )

    assert publish_raw_target(options) == 0
    output = capsys.readouterr().out
    assert "不属于真实 ROS/Gazebo 闭环验证" in output
    assert "capture_stamp: 1750000000.123456789" in output
    assert "target_msgs/msg/RawTarget" in output
    assert "task_id: 4" in output
    assert "sequence_id: 9" in output
    assert "predicted_t_remain: {sec: 1, nanosec: 250000000}" in output


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
